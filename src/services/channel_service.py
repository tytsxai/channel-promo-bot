import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from sqlite3 import IntegrityError
from typing import Any

import aiosqlite

from src.db_utils import get_database_path

logger = logging.getLogger(__name__)
# Keeps shared in-memory DB alive across connections in tests.
_memory_keeper: aiosqlite.Connection | None = None
_memory_keeper_lock = asyncio.Lock()


@asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    db_path, use_uri = get_database_path()
    if use_uri:
        global _memory_keeper
        async with _memory_keeper_lock:
            if _memory_keeper is None:
                _memory_keeper = await aiosqlite.connect(db_path, uri=True)
                await _memory_keeper.execute("PRAGMA journal_mode=WAL")
                await _memory_keeper.execute("PRAGMA busy_timeout=5000")
                await _memory_keeper.execute("PRAGMA foreign_keys=ON")
        db = await aiosqlite.connect(db_path, uri=True)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA busy_timeout=5000")
        await db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
        finally:
            await db.close()
    else:
        db = await aiosqlite.connect(db_path, uri=False)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA busy_timeout=5000")
        await db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
        finally:
            await db.close()


class ChannelService:
    @staticmethod
    async def add_channel(
        chat_id: str,
        title: str,
        username: str | None,
        member_count: int,
        submitted_by: int,
    ) -> int | None:
        async with get_db() as db:
            try:
                cursor = await db.execute(
                    """
                    INSERT INTO channels (chat_id, title, username, member_count, submitted_by)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (chat_id, title, username, member_count, submitted_by),
                )
                await db.commit()
                return cursor.lastrowid
            except IntegrityError:
                logger.warning(f"Channel {chat_id} already exists")
                return None

    @staticmethod
    async def get_pending_channels() -> list[dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM channels WHERE status = ? ORDER BY submitted_at",
                ("pending",),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    async def approve_channel(channel_id: int, approved_by: int, category: str) -> bool:
        async with get_db() as db:
            cursor = await db.execute(
                """
                UPDATE channels SET status = 'approved', approved_by = ?,
                approved_at = CURRENT_TIMESTAMP, category = ? WHERE id = ? AND status = 'pending'
            """,
                (approved_by, category, channel_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    @staticmethod
    async def reject_channel(channel_id: int) -> bool:
        async with get_db() as db:
            cursor = await db.execute(
                "UPDATE channels SET status = 'rejected' WHERE id = ? AND status = 'pending'",
                (channel_id,),
            )
            await db.commit()
            return cursor.rowcount > 0

    @staticmethod
    async def get_channel_by_id(channel_id: int) -> dict[str, Any] | None:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM channels WHERE id = ?", (channel_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    async def channel_exists(chat_id: str) -> bool:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT 1 FROM channels WHERE chat_id = ?", (chat_id,)
            )
            return await cursor.fetchone() is not None

    @staticmethod
    async def get_approved_channels() -> list[dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM channels WHERE status = ? ORDER BY category, title",
                ("approved",),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    async def iter_approved_channels(
        batch_size: int = 500,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream approved channels in deterministic order (OFFSET-based).

        For very large tables, keyset pagination would be more efficient.
        """
        offset = 0
        while True:
            async with get_db() as db:
                cursor = await db.execute(
                    "SELECT * FROM channels WHERE status = ? "
                    "ORDER BY category, title LIMIT ? OFFSET ?",
                    ("approved", batch_size, offset),
                )
                rows = await cursor.fetchall()
            if not rows:
                break
            for row in rows:
                yield dict(row)
            offset += batch_size

    @staticmethod
    async def mark_inactive(chat_id: int) -> bool:
        async with get_db() as db:
            cursor = await db.execute(
                "UPDATE channels SET status = 'inactive' WHERE chat_id = ?",
                (str(chat_id),),
            )
            await db.commit()
            return cursor.rowcount > 0

    @staticmethod
    async def get_pending_count() -> int:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM channels WHERE status = 'pending'"
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    @staticmethod
    async def get_approved_count() -> int:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM channels WHERE status = 'approved'"
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    @staticmethod
    async def get_pending_channels_paginated(
        page: int = 0, per_page: int = 5
    ) -> tuple[list[dict[str, Any]], int]:
        """获取分页的待审核频道列表，返回 (频道列表, 总数)"""
        async with get_db() as db:
            # 获取总数
            cursor = await db.execute(
                "SELECT COUNT(*) FROM channels WHERE status = 'pending'"
            )
            row = await cursor.fetchone()
            total = row[0] if row else 0

            # 获取分页数据
            offset = page * per_page
            cursor = await db.execute(
                "SELECT * FROM channels WHERE status = ? ORDER BY submitted_at LIMIT ? OFFSET ?",
                ("pending", per_page, offset),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows], total
