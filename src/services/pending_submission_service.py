import asyncio
import logging
import time
from typing import Any

from src.services.channel_service import get_db

logger = logging.getLogger(__name__)

_table_ready = False
_table_lock = asyncio.Lock()
_cleanup_lock = asyncio.Lock()
_last_cleanup = 0.0


async def _ensure_table() -> None:
    global _table_ready
    if _table_ready:
        return
    async with _table_lock:
        if _table_ready:
            return
        async with get_db() as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_submissions (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    chat_id TEXT,
                    title TEXT,
                    created_at REAL NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_pending_submissions_created_at
                ON pending_submissions(created_at)
                """
            )
            await db.commit()
        _table_ready = True


class PendingSubmissionService:
    @staticmethod
    async def cleanup_expired(ttl_seconds: int, min_interval: int = 600) -> None:
        """Delete expired submissions; throttled to reduce DB churn."""
        await _ensure_table()
        now = time.time()
        global _last_cleanup
        if now - _last_cleanup < min_interval:
            return
        async with _cleanup_lock:
            now = time.time()
            if now - _last_cleanup < min_interval:
                return
            _last_cleanup = now
            cutoff = now - ttl_seconds
            try:
                async with get_db() as db:
                    await db.execute(
                        "DELETE FROM pending_submissions WHERE created_at < ?",
                        (cutoff,),
                    )
                    await db.commit()
            except Exception:
                logger.exception("Failed to cleanup pending submissions")

    @staticmethod
    async def set_pending_submission(
        user_id: int,
        username: str,
        chat_id: int | None = None,
        title: str | None = None,
    ) -> None:
        await _ensure_table()
        created_at = time.time()
        payload = (
            user_id,
            username,
            str(chat_id) if chat_id is not None else None,
            title,
            created_at,
        )
        async with get_db() as db:
            await db.execute(
                """
                INSERT INTO pending_submissions (user_id, username, chat_id, title, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    chat_id = excluded.chat_id,
                    title = excluded.title,
                    created_at = excluded.created_at
                """,
                payload,
            )
            await db.commit()

    @staticmethod
    async def get_pending_submission(user_id: int) -> dict[str, Any] | None:
        await _ensure_table()
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM pending_submissions WHERE user_id = ?",
                (user_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    async def clear_pending_submission(user_id: int) -> None:
        await _ensure_table()
        async with get_db() as db:
            await db.execute(
                "DELETE FROM pending_submissions WHERE user_id = ?",
                (user_id,),
            )
            await db.commit()
