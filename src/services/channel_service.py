import logging
import aiosqlite
from contextlib import asynccontextmanager
from sqlite3 import IntegrityError
from src.config import config

logger = logging.getLogger(__name__)


@asynccontextmanager
async def get_db():
    db = await aiosqlite.connect(config.database_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA busy_timeout=5000")
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
    async def get_pending_channels() -> list[dict]:
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
                approved_at = CURRENT_TIMESTAMP, category = ? WHERE id = ?
            """,
                (approved_by, category, channel_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    @staticmethod
    async def reject_channel(channel_id: int) -> bool:
        async with get_db() as db:
            cursor = await db.execute(
                "UPDATE channels SET status = 'rejected' WHERE id = ?", (channel_id,)
            )
            await db.commit()
            return cursor.rowcount > 0

    @staticmethod
    async def get_channel_by_id(channel_id: int) -> dict | None:
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
    async def get_approved_channels() -> list[dict]:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM channels WHERE status = ? ORDER BY category, title",
                ("approved",),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

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
    ) -> tuple[list[dict], int]:
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
