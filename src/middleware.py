import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, limit: int = 5, window: int = 60, cleanup_interval: int = 300):
        self.limit = limit
        self.window = window
        self.cleanup_interval = cleanup_interval
        self.requests: dict[int, list[float]] = defaultdict(list)
        self._last_cleanup = time.time()

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
