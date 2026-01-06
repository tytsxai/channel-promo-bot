import html
import logging
import re

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.config import config
from src.services.channel_service import ChannelService
from src.services.pending_submission_service import PendingSubmissionService
from src.utils import LineChunker, escape_markdown

logger = logging.getLogger(__name__)
router = Router()

_PENDING_TTL_SECONDS = 60 * 60  # 1 小时未完成的提交自动过期

# 仅匹配 Telegram 公共用户名（不含 @ 前缀）
_USERNAME_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_]{3,31}")
_AT_USERNAME_RE = re.compile(r"(?<![\w@])@([a-zA-Z][a-zA-Z0-9_]{3,31})")
_TME_USERNAME_RE = re.compile(
    r"(?i)(?:https?://)?(?:t\.me|telegram\.me)/([a-zA-Z][a-zA-Z0-9_]{3,31})"
)
_INVITE_LINK_RE = re.compile(
    r"(?i)(?:https?://)?(?:t\.me|telegram\.me)/(?:joinchat/|\+)"
)
MAX_LIST_MESSAGE_LEN = 4000


async def _cleanup_pending_submissions() -> None:
    # Throttle cleanup to avoid doing DB deletes on every user message.
    await PendingSubmissionService.cleanup_expired(_PENDING_TTL_SECONDS)


def get_help_text(bot_username: str = "") -> str:
    beijing_hour = (config.promo_hour_utc + 8) % 24
    bot_link = f"@{bot_username}" if bot_username else "本机器人"
    # 使用 HTML parse_mode，避免 Markdown 转义遗漏导致 BadRequest。
    bot_link = html.escape(bot_link)
    return (
        "🤖 <b>互推机器人使用指南</b>\n\n"
        "<b>如何提交频道：</b>\n"
        "1️⃣ 直接发送频道链接（如 t.me/yourchannel）\n"
        f"2️⃣ 按提示将 {bot_link} 添加为频道管理员\n"
        "3️⃣ 点击「已添加，验证」完成提交\n"
        "（若链接无法识别，可转发频道任意一条消息给机器人）\n\n"
        "<b>命令列表：</b>\n"
        "/start - 开始使用\n"
        "/submit - 提交频道参与互推\n"
        "/list - 查看已通过审核的频道列表\n"
        "/help - 查看帮助\n\n"
        "<b>参与条件：</b>\n"
        f"• 频道成员数 ≥ {config.min_members}\n"
        "• 机器人需要频道管理员权限\n"
        "• 提交后需等待管理员审核\n\n"
        "<b>互推说明：</b>\n"
        f"每天北京时间 {beijing_hour:02d}:{config.promo_minute:02d}，"
        "机器人会在所有参与的频道发送互推文案。"
    )


@router.message(Command("start"))
async def cmd_start(message: Message, bot: Bot) -> None:
    await message.answer(
        "👋 欢迎使用互推机器人！\n\n"
        "📢 <b>提交频道参与互推：</b>\n"
        "直接发送频道链接即可（如 t.me/yourchannel）\n\n"
        "发送 /help 查看详细帮助",
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: Message, bot: Bot) -> None:
    me = await bot.get_me()
    await message.answer(get_help_text(me.username or ""), parse_mode="HTML")


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
    if not cleaned:
        return None

    if re.fullmatch(_USERNAME_RE, cleaned):
        return cleaned

    match = _AT_USERNAME_RE.search(cleaned)
    if match:
        return match.group(1)

    match = _TME_USERNAME_RE.search(cleaned)
    if match:
        return match.group(1)

    return None


def _contains_invite_link(text: str) -> bool:
    return _INVITE_LINK_RE.search(text) is not None


async def _handle_channel_link(message: Message, text: str, bot: Bot) -> None:
    """处理用户发送的频道链接"""
    user_id = message.from_user.id
    await _cleanup_pending_submissions()

    if _contains_invite_link(text):
        await message.answer(
            "❌ 检测到私密邀请链接，暂不支持。\n\n"
            "请使用公开频道链接：\n"
            "• t.me/yourchannel\n"
            "• @yourchannel"
        )
        return

    username = _extract_username(text)

    if not username:
        await message.answer(
            "❌ 无法识别频道链接\n\n"
            "请发送正确的格式：\n"
            "• t.me/yourchannel\n"
            "• @yourchannel\n"
            "• https://t.me/yourchannel\n"
            "（若链接无法识别，可转发频道任意一条消息）"
        )
        return

    me = await bot.get_me()
    bot_username = me.username or ""

    # 检查是否已提交过
    try:
        chat = await bot.get_chat(f"@{username}")
        if chat.type != "channel":
            await message.answer("❌ 该链接不是频道，请提交频道链接")
            return
        if await ChannelService.channel_exists(str(chat.id)):
            await message.answer("⚠️ 该频道已提交过，请勿重复提交")
            return
    except Exception as e:
        logger.warning("Failed to get chat @%s: %s", username, e)
        await PendingSubmissionService.set_pending_submission(
            user_id=user_id,
            username=username,
        )
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
            f"❌ 无法获取频道 @{username} 的信息\n\n"
            "请确保：\n"
            "• 频道链接正确\n"
            "• 频道是公开的\n"
            "• 机器人已加入频道并具备管理员权限\n\n"
            "如仍失败，请转发频道任意一条消息给机器人。",
            reply_markup=keyboard
        )
        return

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
        await PendingSubmissionService.set_pending_submission(
            user_id=user_id,
            username=username,
            chat_id=chat.id,
            title=chat.title,
        )

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

        title = html.escape(chat.title or "")
        safe_username = html.escape(bot_username)
        await message.answer(
            f"📢 频道: <b>{title}</b>\n\n"
            f"请先将 @{safe_username} 添加为频道管理员：\n\n"
            "1️⃣ 打开频道设置\n"
            "2️⃣ 点击「管理员」\n"
            "3️⃣ 添加管理员 → 搜索 @" + safe_username + "\n"
            "4️⃣ 授予「发送消息」权限\n"
            "5️⃣ 点击下方按钮验证\n",
            reply_markup=keyboard,
            parse_mode="HTML",
        )


async def _verify_and_submit(
    message: Message, chat, username: str, user_id: int, bot: Bot
) -> bool:
    """验证用户身份并提交频道，成功返回 True。"""
    if getattr(chat, "type", None) != "channel":
        await message.answer("❌ 仅支持频道提交，请发送频道链接")
        return False
    # 验证用户是否为管理员
    try:
        member = await bot.get_chat_member(chat.id, user_id)
    except Exception as e:
        logger.warning(f"Failed to verify admin for {chat.id}: {e}")
        await message.answer(
            "❌ 无法验证你的管理员身份\n\n"
            "请确保你是该频道的管理员"
        )
        return False

    if member.status not in ("administrator", "creator"):
        await message.answer("❌ 仅频道管理员可以提交该频道")
        return False

    # 获取成员数
    try:
        member_count = await bot.get_chat_member_count(chat.id)
    except Exception as e:
        logger.warning(f"Failed to get member count for {chat.id}: {e}")
        await message.answer("❌ 无法获取频道成员数")
        return False

    if member_count < config.min_members:
        await message.answer(
            f"❌ 频道成员数不足\n\n"
            f"当前: {member_count} 人\n"
            f"要求: ≥ {config.min_members} 人"
        )
        return False

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
            return True
    except Exception as e:
        logger.error(f"Database error in submit: {e}")
        await message.answer("❌ 系统错误，请稍后重试")
        return False

    logger.info(f"Channel submitted: {username} by user {user_id}")
    await message.answer(
        f"✅ 频道提交成功！\n\n"
        f"📢 {chat.title}\n"
        f"👥 成员数: {member_count}\n\n"
        "请等待管理员审核，审核通过后将加入互推列表。"
    )
    return True


@router.callback_query(F.data.startswith("verify:"))
async def callback_verify(callback: CallbackQuery, bot: Bot) -> None:
    """处理验证回调"""
    user_id = callback.from_user.id
    username = callback.data.split(":", 1)[1]
    await _cleanup_pending_submissions()

    try:
        pending = await PendingSubmissionService.get_pending_submission(user_id)
        chat_id = pending.get("chat_id") if pending else None
        if chat_id:
            chat = await bot.get_chat(chat_id)
        else:
            chat = await bot.get_chat(f"@{username}")
    except Exception as e:
        logger.warning("Verify failed to get chat @%s: %s", username, e)
        await callback.answer(
            "❌ 无法获取频道信息，请确认机器人已加入频道后重试", show_alert=True
        )
        return
    if getattr(chat, "type", None) != "channel":
        await callback.answer("❌ 仅支持频道提交", show_alert=True)
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
    success = await _verify_and_submit(callback.message, chat, username, user_id, bot)

    if success:
        await PendingSubmissionService.clear_pending_submission(user_id)

        # 删除引导消息
        try:
            await callback.message.delete()
        except Exception:
            pass


@router.callback_query(F.data == "cancel_submit")
async def callback_cancel(callback: CallbackQuery) -> None:
    """取消提交"""
    user_id = callback.from_user.id
    await _cleanup_pending_submissions()
    await PendingSubmissionService.clear_pending_submission(user_id)
    await callback.answer("已取消")
    try:
        await callback.message.delete()
    except Exception:
        pass


# 处理直接发送的链接消息
@router.message(F.forward_from_chat)
async def handle_forwarded_channel(message: Message, bot: Bot) -> None:
    chat = message.forward_from_chat
    if not chat or chat.type != "channel":
        return
    await _cleanup_pending_submissions()

    if not chat.username:
        await message.answer(
            "❌ 该频道没有公开用户名，暂不支持。\n\n"
            "请将频道设置为公开并提供 @username。"
        )
        return

    user_id = message.from_user.id

    if await ChannelService.channel_exists(str(chat.id)):
        await message.answer("⚠️ 该频道已提交过，请勿重复提交")
        return

    me = await bot.get_me()
    bot_username = me.username or ""

    try:
        bot_member = await bot.get_chat_member(chat.id, me.id)
        bot_in_channel = bot_member.status in ("administrator", "creator")
    except Exception:
        bot_in_channel = False

    if bot_in_channel:
        await _verify_and_submit(message, chat, chat.username, user_id, bot)
        return

    await PendingSubmissionService.set_pending_submission(
        user_id=user_id,
        username=chat.username,
        chat_id=chat.id,
        title=chat.title,
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ 已添加，验证",
            callback_data=f"verify:{chat.username}"
        )],
        [InlineKeyboardButton(
            text="❌ 取消",
            callback_data="cancel_submit"
        )]
    ])

    title = html.escape(chat.title or "")
    safe_username = html.escape(bot_username)
    await message.answer(
        f"📢 频道: <b>{title}</b>\n\n"
        f"请先将 @{safe_username} 添加为频道管理员：\n\n"
        "1️⃣ 打开频道设置\n"
        "2️⃣ 点击「管理员」\n"
        "3️⃣ 添加管理员 → 搜索 @" + safe_username + "\n"
        "4️⃣ 授予「发送消息」权限\n"
        "5️⃣ 点击下方按钮验证\n",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_message(message: Message, bot: Bot) -> None:
    """处理用户直接发送的文本（可能是频道链接）"""
    text = message.text.strip()

    # 检查是否像频道链接
    if _contains_invite_link(text):
        await message.answer(
            "❌ 检测到私密邀请链接，暂不支持。\n\n"
            "请使用公开频道链接：\n"
            "• t.me/yourchannel\n"
            "• @yourchannel"
        )
        return

    if _extract_username(text):
        await _handle_channel_link(message, text, bot)
        return

    if any(token in text for token in ("t.me", "telegram.me", "@")):
        await _handle_channel_link(message, text, bot)
        return


@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    try:
        total = await ChannelService.get_approved_count()
    except Exception as e:
        logger.error(f"Failed to get channels: {e}")
        await message.answer("❌ 获取频道列表失败，请稍后重试")
        return

    if total == 0:
        await message.answer("📭 暂无已审核通过的频道")
        return

    # MarkdownV2 输出必须转义动态字段（分类/标题/用户名），并按类别流式输出以控内存。
    chunker = LineChunker(MAX_LIST_MESSAGE_LEN)
    for text in chunker.add_line("📋 *互推频道列表*"):
        await message.answer(text, parse_mode="MarkdownV2")

    current_category: str | None = None
    async for ch in ChannelService.iter_approved_channels(config.promo_batch_size):
        cat = ch["category"] or "其他"
        if cat != current_category:
            for text in chunker.add_line(""):
                await message.answer(text, parse_mode="MarkdownV2")
            for text in chunker.add_line(f"*{escape_markdown(cat)}*"):
                await message.answer(text, parse_mode="MarkdownV2")
            current_category = cat

        title = escape_markdown(ch["title"])
        link = f"@{escape_markdown(ch['username'])}" if ch["username"] else title
        for text in chunker.add_line(f"• {title} \\- {link}"):
            await message.answer(text, parse_mode="MarkdownV2")

    for text in chunker.flush():
        await message.answer(text, parse_mode="MarkdownV2")
