import logging
import os
from collections.abc import Awaitable, Callable

import aiosqlite

from src.config import config
from src.db_utils import get_database_path

logger = logging.getLogger(__name__)


MigrationFn = Callable[[aiosqlite.Connection], Awaitable[None]]


async def _migration_v1(db: aiosqlite.Connection) -> None:
    await db.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            username TEXT,
            member_count INTEGER DEFAULT 0,
            category TEXT,
            status TEXT DEFAULT 'pending',
            submitted_by INTEGER NOT NULL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_at TIMESTAMP,
            approved_by INTEGER
        )
    """)
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_channels_status ON channels(status)
    """)
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_channels_category ON channels(category)
    """)


async def _migration_v2(db: aiosqlite.Connection) -> None:
    await db.execute("""
        CREATE TABLE IF NOT EXISTS pending_submissions (
            user_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            chat_id TEXT,
            title TEXT,
            created_at REAL NOT NULL
        )
    """)
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_pending_submissions_created_at
        ON pending_submissions(created_at)
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS rate_limit_requests (
            user_id INTEGER NOT NULL,
            ts REAL NOT NULL
        )
    """)
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_rate_limit_user_ts
        ON rate_limit_requests(user_id, ts)
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS distributed_locks (
            name TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            expires_at REAL NOT NULL
        )
    """)


async def _migration_v3(db: aiosqlite.Connection) -> None:
    await db.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            name TEXT PRIMARY KEY,
            value INTEGER NOT NULL DEFAULT 0,
            updated_at REAL NOT NULL
        )
    """)


MIGRATIONS: list[tuple[int, MigrationFn]] = [
    (1, _migration_v1),
    (2, _migration_v2),
    (3, _migration_v3),
]


async def _apply_migrations(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA user_version")
    row = await cursor.fetchone()
    current_version = row[0] if row else 0

    for version, migration in MIGRATIONS:
        if current_version < version:
            logger.info("Applying DB migration v%s", version)
            await migration(db)
            await db.execute(f"PRAGMA user_version={version}")
            current_version = version


async def init_db() -> None:
    db_path, use_uri = get_database_path(config.database_path)
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    async with aiosqlite.connect(db_path, uri=use_uri) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
        await _apply_migrations(db)
        await db.commit()
