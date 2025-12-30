import logging
import re
from urllib.parse import urlparse

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from src.config import config
from src.services.channel_service import ChannelService
from src.utils import escape_markdown

logger = logging.getLogger(__name__)
router = Router()


def get_help_text() -> str:
    beijing_hour = (config.promo_hour_utc + 8) % 24
    return f"""🤖 **互推机器人使用指南**

**用户命令：**
/start - 开始使用
/submit <频道链接> - 提交频道参与互推
/list - 查看已通过审核的频道列表

**参与条件：**
• 频道/群组成员数 ≥ {config.min_members}
• 提交后需等待管理员审核

**互推说明：**
每天北京时间 {beijing_hour:02d}:{config.promo_minute:02d}，机器人会在所有参与的频道发送互推文案。
"""


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 欢迎使用互推机器人！\n\n"
        "发送 /submit <频道链接> 提交你的频道\n"
        "发送 /help 查看详细帮助"
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(get_help_text(), parse_mode="Markdown")


@router.message(Command("submit"))
async def cmd_submit(message: Message, command: CommandObject, bot: Bot) -> None:
    user_id = message.from_user.id

    if not command.args:
        await message.answer(
            "❌ 请提供频道链接\n用法: /submit @channel 或 /submit https://t.me/channel"
        )
        return

    username = _extract_username(command.args.strip())
    if not username:
        await message.answer("❌ 无效的频道链接格式")
        return

    try:
        chat = await bot.get_chat(f"@{username}")
    except Exception as e:
        logger.warning(f"Failed to get chat @{username}: {e}")
        await message.answer("❌ 无法获取频道信息，请确保链接正确且频道为公开")
        return

    try:
        member = await bot.get_chat_member(chat.id, user_id)
    except Exception as e:
        logger.warning(f"Failed to verify admin for {chat.id}: {e}")
        await message.answer("❌ 无法验证你是否为频道管理员，请确保机器人已加入频道并具备权限")
        return

    if member.status not in ("administrator", "creator"):
        await message.answer("❌ 仅频道管理员可以提交该频道")
        return

    try:
        member_count = await bot.get_chat_member_count(chat.id)
    except Exception as e:
        logger.warning(f"Failed to get member count for {chat.id}: {e}")
        await message.answer("❌ 无法获取频道成员数")
        return

    if member_count < config.min_members:
        await message.answer(
            f"❌ 频道成员数 ({member_count}) 不足 {config.min_members}，暂不符合互推条件"
        )
        return

    try:
        if await ChannelService.channel_exists(str(chat.id)):
            await message.answer("⚠️ 该频道已提交过，请勿重复提交")
            return

        await ChannelService.add_channel(
            chat_id=str(chat.id),
            title=chat.title or username,
            username=username,
            member_count=member_count,
            submitted_by=user_id,
        )
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
