import asyncio
import logging
import time
from typing import Any

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNotFound,
    TelegramRetryAfter,
)

from src.config import config
from src.services.channel_service import ChannelService
from src.services.metrics_service import record_promo_run
from src.utils import LineChunker, chunk_lines, escape_markdown

logger = logging.getLogger(__name__)
MAX_MESSAGE_LEN = 4000


class SendLimiter:
    def __init__(self, min_interval: float):
        self._min_interval = max(0.0, min_interval)
        self._lock = asyncio.Lock()
        self._next_time = 0.0

    async def wait_turn(self) -> None:
        if self._min_interval <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            if now < self._next_time:
                await asyncio.sleep(self._next_time - now)
                now = time.monotonic()
            self._next_time = now + self._min_interval

    async def impose_cooldown(self, seconds: float) -> None:
        if seconds <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            self._next_time = max(self._next_time, now + seconds)


async def send_promo_to_all(
    bot: Bot, cancel_event: asyncio.Event | None = None
) -> tuple[int, int]:
    total = await ChannelService.get_approved_count()
    if total == 0:
        logger.info("No approved channels, skipping promo")
        await record_promo_run(0, 0, 0, cancelled=False, empty_run=True)
        return 0, 0
    if cancel_event and cancel_event.is_set():
        logger.warning("Promo broadcast cancelled before start")
        await record_promo_run(total, 0, total, cancelled=True, empty_run=False)
        return 0, total

    sent_count = 0
    failed_count = 0
    count_lock = asyncio.Lock()
    metrics_recorded = False
    producer: asyncio.Task[None] | None = None
    workers: list[asyncio.Task[None]] = []

    try:
        # Build once and broadcast to all channels to avoid repeated DB scans.
        messages = await _build_promo_messages_from_db()
        limiter = SendLimiter(config.promo_send_interval)
        worker_count = max(1, config.promo_concurrency)
        # Bounded queue keeps memory stable when channel count is large.
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(
            maxsize=worker_count * 4
        )

        async def _send_to_channel(ch: dict[str, Any]) -> bool:
            try:
                chat_id = int(ch["chat_id"])
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid chat_id in channel record: %s", ch.get("chat_id")
                )
                return False

            try:
                for text in messages:
                    success = await _send_with_retry(bot, chat_id, text, limiter=limiter)
                    if not success:
                        return False
                return True
            except Exception as exc:
                logger.error("Send failed for %s: %s", chat_id, exc)
                return False

        async def _producer() -> None:
            try:
                async for ch in ChannelService.iter_approved_channel_targets(
                    config.promo_batch_size
                ):
                    if cancel_event and cancel_event.is_set():
                        break
                    await queue.put(ch)
            finally:
                for _ in range(worker_count):
                    await queue.put(None)

        async def _worker() -> None:
            nonlocal sent_count, failed_count
            while True:
                ch = await queue.get()
                if ch is None:
                    queue.task_done()
                    return
                if cancel_event and cancel_event.is_set():
                    async with count_lock:
                        failed_count += 1
                    queue.task_done()
                    continue
                ok = await _send_to_channel(ch)
                async with count_lock:
                    if ok:
                        sent_count += 1
                    else:
                        failed_count += 1
                queue.task_done()

        producer = asyncio.create_task(_producer())
        workers = [asyncio.create_task(_worker()) for _ in range(worker_count)]

        producer_error: Exception | None = None
        try:
            await producer
        except Exception as exc:
            producer_error = exc
            logger.exception("Promo producer failed")

        await queue.join()
        worker_results = await asyncio.gather(*workers, return_exceptions=True)
        for result in worker_results:
            if isinstance(result, Exception):
                logger.error("Promo worker failed: %s", result)
                if producer_error is None:
                    producer_error = result

        cancelled = bool(cancel_event and cancel_event.is_set())
        if cancelled:
            failed_count = total - sent_count
            logger.warning("Promo broadcast stopped early due to cancellation")

        if producer_error is not None:
            failed_count = max(failed_count, total - sent_count)

        logger.info(f"Promo broadcast: {sent_count} sent, {failed_count} failed")
        await record_promo_run(
            total,
            sent_count,
            failed_count,
            cancelled=cancelled,
            empty_run=False,
        )
        metrics_recorded = True

        if producer_error is not None:
            raise producer_error
        return sent_count, failed_count
    except Exception:
        if not metrics_recorded:
            try:
                await record_promo_run(
                    total,
                    sent_count,
                    max(failed_count, total - sent_count),
                    cancelled=bool(cancel_event and cancel_event.is_set()),
                    empty_run=False,
                )
            except Exception as metric_exc:
                logger.warning("Failed to record promo metrics after error: %s", metric_exc)
        raise
    finally:
        if producer is not None and not producer.done():
            producer.cancel()
            await asyncio.gather(producer, return_exceptions=True)
        if workers:
            for worker in workers:
                if not worker.done():
                    worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)


def _build_promo_lines(channels: list[dict[str, Any]]) -> list[str]:
    grouped: dict[str, list] = {}
    for ch in channels:
        cat = ch["category"] or "其他"
        grouped.setdefault(cat, []).append(ch)

    lines = ["🔥 *今日互推精选* 🔥", ""]

    for cat, chs in grouped.items():
        lines.append(f"📁 *{escape_markdown(cat)}*")
        for ch in chs:
            # MarkdownV2 对动态文本和 URL 都需要转义，避免 BadRequest。
            title = escape_markdown(ch["title"])
            if ch["username"]:
                safe_username = escape_markdown(ch["username"])
                lines.append(f"👉 [{title}](https://t.me/{safe_username})")
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
    return chunk_lines(lines, limit)


async def _build_promo_messages_from_db() -> list[str]:
    # Stream lines from DB to avoid loading large channel lists into memory.
    messages: list[str] = []
    chunker = LineChunker(MAX_MESSAGE_LEN)

    def _append_line(line: str) -> None:
        messages.extend(chunker.add_line(line))

    current_category: str | None = None
    _append_line("🔥 *今日互推精选* 🔥")
    _append_line("")

    async for ch in ChannelService.iter_approved_channels(config.promo_batch_size):
        cat = ch["category"] or "其他"
        if cat != current_category:
            if current_category is not None:
                _append_line("")
            _append_line(f"📁 *{escape_markdown(cat)}*")
            current_category = cat
        title = escape_markdown(ch["title"])
        if ch["username"]:
            safe_username = escape_markdown(ch["username"])
            _append_line(f"👉 [{title}](https://t.me/{safe_username})")
        else:
            _append_line(f"👉 {title}")

    _append_line("")
    _append_line("─" * 20)
    _append_line("💡 想加入互推？私聊机器人发送 /help 了解详情")
    messages.extend(chunker.flush())
    return messages


async def _send_with_retry(
    bot: Bot,
    chat_id: int,
    text: str,
    max_retries: int = 3,
    limiter: SendLimiter | None = None,
) -> bool:
    for attempt in range(max_retries):
        try:
            if limiter:
                await limiter.wait_turn()
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True,
            )
            return True
        except TelegramRetryAfter as e:
            logger.warning(f"Rate limited, waiting {e.retry_after}s")
            if limiter:
                await limiter.impose_cooldown(e.retry_after)
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
