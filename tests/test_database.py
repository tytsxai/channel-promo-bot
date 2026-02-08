from dataclasses import replace

import aiosqlite
import pytest

import src.models.database as database
from src.config import config as base_config


class TestDatabaseInit:
    @pytest.fixture
    def temp_db_path(self, tmp_path, monkeypatch):
        db_path = tmp_path / "data" / "bot.db"
        cfg = replace(base_config, database_path=str(db_path))
        monkeypatch.setattr(database, "config", cfg)
        return db_path

    @pytest.mark.asyncio
    async def test_init_db_creates_schema(self, temp_db_path):
        await database.init_db()

        async with aiosqlite.connect(temp_db_path) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='channels'"
            )
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "channels"
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='pending_submissions'"
            )
            row = await cursor.fetchone()
            assert row is not None
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='rate_limit_requests'"
            )
            row = await cursor.fetchone()
            assert row is not None
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='distributed_locks'"
            )
            row = await cursor.fetchone()
            assert row is not None
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='metrics'"
            )
            row = await cursor.fetchone()
            assert row is not None

    @pytest.mark.asyncio
    async def test_init_db_creates_indexes_and_version(self, temp_db_path):
        await database.init_db()

        async with aiosqlite.connect(temp_db_path) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
            rows = await cursor.fetchall()
            index_names = {r[0] for r in rows}
            assert "idx_channels_status" in index_names
            assert "idx_channels_category" in index_names

            cursor = await db.execute("PRAGMA user_version")
            row = await cursor.fetchone()
            assert row[0] == 3
