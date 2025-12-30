import asyncio
import logging
from typing import Any

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNotFound,
    TelegramRetryAfter,
)

from src.services.channel_service import ChannelService
from src.utils import escape_markdown

logger = logging.getLogger(__name__)
MAX_MESSAGE_LEN = 4000


async def send_promo_to_all(bot: Bot) -> tuple[int, int]:
    channels = await ChannelService.get_approved_channels()
    if not channels:
        logger.info("No approved channels, skipping promo")
        return 0, 0

    messages = _build_promo_messages(channels)
    sent_count = 0
    failed_count = 0

    for ch in channels:
        try:
            chat_id = int(ch["chat_id"])
        except (TypeError, ValueError):
            logger.warning("Invalid chat_id in channel record: %s", ch.get("chat_id"))
            failed_count += 1
            continue
        success = True
        for text in messages:
            success = await _send_with_retry(bot, chat_id, text)
            if not success:
                break
            await asyncio.sleep(0.05)
        if success:
            sent_count += 1
        else:
            failed_count += 1
        await asyncio.sleep(0.1)

    logger.info(f"Promo broadcast: {sent_count} sent, {failed_count} failed")
    return sent_count, failed_count


def _build_promo_lines(channels: list[dict[str, Any]]) -> list[str]:
    grouped: dict[str, list] = {}
    for ch in channels:
        cat = ch["category"] or "其他"
        grouped.setdefault(cat, []).append(ch)

    lines = ["🔥 *今日互推精选* 🔥", ""]

    for cat, chs in grouped.items():
        lines.append(f"📁 *{escape_markdown(cat)}*")
        for ch in chs:
            title = escape_markdown(ch['title'])
            if ch["username"]:
                lines.append(f"👉 [{title}](https://t.me/{ch['username']})")
            else:
                lines.append(f"👉 {title}")
        lines.append("")

    lines.append("─" * 20)
    lines.append("💡 想加入互推？私聊机器人发送 /help 了解详情")

    return lines


def _build_promo_text(channels: list[dict[str, Any]]) -> str:
    return "\n".join(_build_promo_lines(channels))


def _build_promo_messages(channels: list[dict[str, Any]]) -> list[str]:
    lines = _build_promo_lines(channels)
    return _chunk_lines(lines, MAX_MESSAGE_LEN)


def _chunk_lines(lines: list[str], limit: int) -> list[str]:
    messages: list[str] = []
    buffer: list[str] = []
    length = 0

    for line in lines:
        if len(line) > limit:
            if buffer:
                messages.append("\n".join(buffer))
                buffer = []
                length = 0
            for i in range(0, len(line), limit):
                messages.append(line[i : i + limit])
            continue

        extra = len(line) + (1 if buffer else 0)
        if length + extra > limit:
            messages.append("\n".join(buffer))
            buffer = [line]
            length = len(line)
        else:
            buffer.append(line)
            length += extra

    if buffer:
        messages.append("\n".join(buffer))

    return messages


async def _send_with_retry(
    bot: Bot, chat_id: int, text: str, max_retries: int = 3
) -> bool:
    for attempt in range(max_retries):
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True,
            )
            return True
        except TelegramRetryAfter as e:
            logger.warning(f"Rate limited, waiting {e.retry_after}s")
            await asyncio.sleep(e.retry_after)
        except TelegramForbiddenError:
            logger.warning(f"Bot removed from channel {chat_id}, marking inactive")
            await ChannelService.mark_inactive(chat_id)
            return False
        except TelegramNotFound:
            logger.warning(f"Channel {chat_id} not found, marking inactive")
            await ChannelService.mark_inactive(chat_id)
            return False
        except TelegramBadRequest as e:
            logger.error(f"Bad request to {chat_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Send failed to {chat_id} (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
    return False
