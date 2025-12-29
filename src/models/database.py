import logging
import os
import aiosqlite
from src.config import config

logger = logging.getLogger(__name__)


async def init_db():
    db_path = config.database_path
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
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
        await db.commit()
