import asyncio
import logging
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message

from src.services.channel_service import get_db

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    def __init__(
        self,
        limit: int = 5,
        window: int = 60,
        cleanup_interval: int = 300,
        storage: str = "memory",
    ):
        self.limit = limit
        self.window = window
        self.cleanup_interval = cleanup_interval
        self.storage = storage.lower()
        if self.storage not in {"memory", "sqlite"}:
            raise ValueError("storage must be 'memory' or 'sqlite'")
        self.requests: dict[int, list[float]] = defaultdict(list)
        self._last_cleanup = time.time()
        self._sqlite_ready = False
        self._sqlite_lock = asyncio.Lock()

    def _cleanup_stale_entries(self, now: float) -> None:
        """清理过期的用户记录，防止内存泄漏"""
        if now - self._last_cleanup < self.cleanup_interval:
            return

        stale_users = [
            uid for uid, times in self.requests.items()
            if not times or now - max(times) > self.window
        ]
        for uid in stale_users:
            del self.requests[uid]
        self._last_cleanup = now

    async def _allow_sqlite(self, user_id: int, now: float) -> bool:
        window_start = now - self.window
        try:
            # SQLite backend favors correctness over throughput; failures are fail-open.
            if not self._sqlite_ready:
                async with self._sqlite_lock:
                    if not self._sqlite_ready:
                        async with get_db() as db:
                            await db.execute(
                                """
                                CREATE TABLE IF NOT EXISTS rate_limit_requests (
                                    user_id INTEGER NOT NULL,
                                    ts REAL NOT NULL
                                )
                                """
                            )
                            await db.execute(
                                """
                                CREATE INDEX IF NOT EXISTS idx_rate_limit_user_ts
                                ON rate_limit_requests(user_id, ts)
                                """
                            )
                            await db.commit()
                        self._sqlite_ready = True
            async with get_db() as db:
                await db.execute("BEGIN IMMEDIATE")
                if now - self._last_cleanup >= self.cleanup_interval:
                    await db.execute(
                        "DELETE FROM rate_limit_requests WHERE ts < ?",
                        (window_start,),
                    )
                    self._last_cleanup = now

                cursor = await db.execute(
                    "SELECT COUNT(*) FROM rate_limit_requests WHERE user_id = ? AND ts >= ?",
                    (user_id, window_start),
                )
                row = await cursor.fetchone()
                count = row[0] if row else 0
                if count >= self.limit:
                    await db.commit()
                    return False

                await db.execute(
                    "INSERT INTO rate_limit_requests (user_id, ts) VALUES (?, ?)",
                    (user_id, now),
                )
                await db.commit()
                return True
        except Exception as exc:
            logger.warning("Rate limit storage failed: %s", exc)
            return True

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or not event.from_user:
            return await handler(event, data)

        user_id = event.from_user.id
        now = time.time()

        if self.storage == "sqlite":
            allowed = await self._allow_sqlite(user_id, now)
            if not allowed:
                await event.answer("⚠️ 请求过于频繁，请稍后再试")
                return
            return await handler(event, data)

        # 定期清理过期记录
        self._cleanup_stale_entries(now)

        self.requests[user_id] = [
            t for t in self.requests[user_id] if now - t < self.window
        ]

        if len(self.requests[user_id]) >= self.limit:
            await event.answer("⚠️ 请求过于频繁，请稍后再试")
            return

        self.requests[user_id].append(now)
        return await handler(event, data)
