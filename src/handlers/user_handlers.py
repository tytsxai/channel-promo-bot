import logging
import re
from urllib.parse import urlparse

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.config import config
from src.services.channel_service import ChannelService
from src.utils import escape_markdown

logger = logging.getLogger(__name__)
router = Router()

# 临时存储待确认的频道信息 {user_id: {username, chat_id, title, member_count}}
_pending_submissions: dict[int, dict] = {}


def get_help_text(bot_username: str = "") -> str:
    beijing_hour = (config.promo_hour_utc + 8) % 24
    bot_link = f"@{bot_username}" if bot_username else "本机器人"
    return f"""🤖 **互推机器人使用指南**

**如何提交频道：**
1️⃣ 直接发送频道链接（如 t.me/yourchannel）
2️⃣ 按提示将 {bot_link} 添加为频道管理员
3️⃣ 点击「已添加，验证」完成提交

**命令列表：**
/start - 开始使用
/list - 查看已通过审核的频道列表
/help - 查看帮助

**参与条件：**
• 频道成员数 ≥ {config.min_members}
• 机器人需要频道管理员权限
• 提交后需等待管理员审核

**互推说明：**
每天北京时间 {beijing_hour:02d}:{config.promo_minute:02d}，机器人会在所有参与的频道发送互推文案。
"""


@router.message(Command("start"))
async def cmd_start(message: Message, bot: Bot) -> None:
    me = await bot.get_me()
    await message.answer(
        "👋 欢迎使用互推机器人！\n\n"
        "📢 **提交频道参与互推：**\n"
        "直接发送频道链接即可（如 t.me/yourchannel）\n\n"
        f"发送 /help 查看详细帮助",
        parse_mode="Markdown"
    )


@router.message(Command("help"))
async def cmd_help(message: Message, bot: Bot) -> None:
    me = await bot.get_me()
    await message.answer(get_help_text(me.username or ""), parse_mode="Markdown")


@router.message(Command("submit"))
async def cmd_submit(message: Message, command: CommandObject, bot: Bot) -> None:
    """处理 /submit 命令，兼容旧用法"""
    if command.args:
        await _handle_channel_link(message, command.args.strip(), bot)
    else:
        await message.answer(
            "📢 请直接发送频道链接\n\n"
            "例如：t.me/yourchannel 或 @yourchannel"
        )


def _extract_username(text: str) -> str | None:
    cleaned = text.strip()
    if cleaned.startswith("@"):
        cleaned = cleaned[1:]

    username = cleaned
    if cleaned.startswith(("http://", "https://")):
        parsed = urlparse(cleaned)
        if parsed.netloc not in {"t.me", "telegram.me"}:
            return None
        username = parsed.path.lstrip("/").split("/")[0]
    elif cleaned.startswith("t.me/"):
        username = cleaned.replace("t.me/", "", 1).split("/")[0]

    username = username.split("?")[0].split("#")[0]
    if not username:
        return None

    match = re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{3,31}", username)
    return match.group(0) if match else None


async def _handle_channel_link(message: Message, text: str, bot: Bot) -> None:
    """处理用户发送的频道链接"""
    user_id = message.from_user.id
    username = _extract_username(text)

    if not username:
        await message.answer(
            "❌ 无法识别频道链接\n\n"
            "请发送正确的格式：\n"
            "• t.me/yourchannel\n"
            "• @yourchannel\n"
            "• https://t.me/yourchannel"
        )
        return

    # 检查是否已提交过
    try:
        chat = await bot.get_chat(f"@{username}")
        if await ChannelService.channel_exists(str(chat.id)):
            await message.answer("⚠️ 该频道已提交过，请勿重复提交")
            return
    except Exception as e:
        logger.warning(f"Failed to get chat @{username}: {e}")
        await message.answer(
            f"❌ 无法获取频道 @{username} 的信息\n\n"
            "请确保：\n"
            "• 频道链接正确\n"
            "• 频道是公开的"
        )
        return

    me = await bot.get_me()
    bot_username = me.username

    # 检查机器人是否已在频道中
    try:
        bot_member = await bot.get_chat_member(chat.id, me.id)
        bot_in_channel = bot_member.status in ("administrator", "creator")
    except Exception:
        bot_in_channel = False

    if bot_in_channel:
        # 机器人已在频道，直接验证用户身份
        await _verify_and_submit(message, chat, username, user_id, bot)
    else:
        # 机器人不在频道，引导用户添加
        _pending_submissions[user_id] = {"username": username, "chat_id": chat.id}

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ 已添加，验证",
                callback_data=f"verify:{username}"
            )],
            [InlineKeyboardButton(
                text="❌ 取消",
                callback_data="cancel_submit"
            )]
        ])

        await message.answer(
            f"📢 频道: **{chat.title}**\n\n"
            f"请先将 @{bot_username} 添加为频道管理员：\n\n"
            "1️⃣ 打开频道设置\n"
            "2️⃣ 点击「管理员」\n"
            "3️⃣ 添加管理员 → 搜索 @" + bot_username + "\n"
            "4️⃣ 授予「发送消息」权限\n"
            "5️⃣ 点击下方按钮验证\n",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )


async def _verify_and_submit(
    message: Message, chat, username: str, user_id: int, bot: Bot
) -> None:
    """验证用户身份并提交频道"""
    # 验证用户是否为管理员
    try:
        member = await bot.get_chat_member(chat.id, user_id)
    except Exception as e:
        logger.warning(f"Failed to verify admin for {chat.id}: {e}")
        await message.answer(
            "❌ 无法验证你的管理员身份\n\n"
            "请确保你是该频道的管理员"
        )
        return

    if member.status not in ("administrator", "creator"):
        await message.answer("❌ 仅频道管理员可以提交该频道")
        return

    # 获取成员数
    try:
        member_count = await bot.get_chat_member_count(chat.id)
    except Exception as e:
        logger.warning(f"Failed to get member count for {chat.id}: {e}")
        await message.answer("❌ 无法获取频道成员数")
        return

    if member_count < config.min_members:
        await message.answer(
            f"❌ 频道成员数不足\n\n"
            f"当前: {member_count} 人\n"
            f"要求: ≥ {config.min_members} 人"
        )
        return

    # 保存到数据库
    try:
        channel_id = await ChannelService.add_channel(
            chat_id=str(chat.id),
            title=chat.title or username,
            username=username,
            member_count=member_count,
            submitted_by=user_id,
        )
        if channel_id is None:
            await message.answer("⚠️ 该频道已提交过，请勿重复提交")
            return
    except Exception as e:
        logger.error(f"Database error in submit: {e}")
        await message.answer("❌ 系统错误，请稍后重试")
        return

    logger.info(f"Channel submitted: {username} by user {user_id}")
    await message.answer(
        f"✅ 频道提交成功！\n\n"
        f"📢 {chat.title}\n"
        f"👥 成员数: {member_count}\n\n"
        "请等待管理员审核，审核通过后将加入互推列表。"
    )


@router.callback_query(F.data.startswith("verify:"))
async def callback_verify(callback: CallbackQuery, bot: Bot) -> None:
    """处理验证回调"""
    user_id = callback.from_user.id
    username = callback.data.split(":", 1)[1]

    try:
        chat = await bot.get_chat(f"@{username}")
    except Exception:
        await callback.answer("❌ 频道不存在", show_alert=True)
        return

    # 检查机器人是否已添加
    me = await bot.get_me()
    try:
        bot_member = await bot.get_chat_member(chat.id, me.id)
        if bot_member.status not in ("administrator", "creator"):
            await callback.answer(
                "❌ 机器人还不是管理员，请先添加", show_alert=True
            )
            return
    except Exception:
        await callback.answer(
            "❌ 机器人还未加入频道，请先添加", show_alert=True
        )
        return

    await callback.answer("验证中...")
    await _verify_and_submit(callback.message, chat, username, user_id, bot)

    # 清理待确认数据
    _pending_submissions.pop(user_id, None)

    # 删除引导消息
    try:
        await callback.message.delete()
    except Exception:
        pass


@router.callback_query(F.data == "cancel_submit")
async def callback_cancel(callback: CallbackQuery) -> None:
    """取消提交"""
    user_id = callback.from_user.id
    _pending_submissions.pop(user_id, None)
    await callback.answer("已取消")
    try:
        await callback.message.delete()
    except Exception:
        pass


# 处理直接发送的链接消息
@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_message(message: Message, bot: Bot) -> None:
    """处理用户直接发送的文本（可能是频道链接）"""
    text = message.text.strip()

    # 检查是否像频道链接
    if _extract_username(text):
        await _handle_channel_link(message, text, bot)


@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    try:
        channels = await ChannelService.get_approved_channels()
    except Exception as e:
        logger.error(f"Failed to get channels: {e}")
        await message.answer("❌ 获取频道列表失败，请稍后重试")
        return

    if not channels:
        await message.answer("📭 暂无已审核通过的频道")
        return

    grouped: dict[str, list] = {}
    for ch in channels:
        cat = ch["category"] or "其他"
        grouped.setdefault(cat, []).append(ch)

    lines = ["📋 *互推频道列表*\n"]
    for cat, chs in grouped.items():
        lines.append(f"\n*{escape_markdown(cat)}*")
        for ch in chs:
            title = escape_markdown(ch['title'])
            link = f"@{escape_markdown(ch['username'])}" if ch["username"] else title
            lines.append(f"• {title} \\- {link}")

    await message.answer("\n".join(lines), parse_mode="MarkdownV2")
