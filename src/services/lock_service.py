import asyncio
import time

from src.services.channel_service import get_db

_table_ready = False
_table_lock = asyncio.Lock()


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
                CREATE TABLE IF NOT EXISTS distributed_locks (
                    name TEXT PRIMARY KEY,
                    owner TEXT NOT NULL,
                    expires_at REAL NOT NULL
                )
                """
            )
            await db.commit()
        _table_ready = True


async def acquire_lock(name: str, owner: str, ttl_seconds: int) -> bool:
    await _ensure_table()
    now = time.time()
    expires_at = now + ttl_seconds
    async with get_db() as db:
        cursor = await db.execute(
            """
            INSERT INTO distributed_locks (name, owner, expires_at)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                owner = excluded.owner,
                expires_at = excluded.expires_at
            WHERE distributed_locks.expires_at <= ? OR distributed_locks.owner = ?
            """,
            (name, owner, expires_at, now, owner),
        )
        await db.commit()
        return cursor.rowcount > 0


async def refresh_lock(name: str, owner: str, ttl_seconds: int) -> bool:
    await _ensure_table()
    now = time.time()
    expires_at = now + ttl_seconds
    async with get_db() as db:
        cursor = await db.execute(
            """
            UPDATE distributed_locks
            SET expires_at = ?
            WHERE name = ? AND owner = ?
            """,
            (expires_at, name, owner),
        )
        await db.commit()
        return cursor.rowcount > 0


async def release_lock(name: str, owner: str) -> None:
    await _ensure_table()
    async with get_db() as db:
        await db.execute(
            "DELETE FROM distributed_locks WHERE name = ? AND owner = ?",
            (name, owner),
        )
        await db.commit()
