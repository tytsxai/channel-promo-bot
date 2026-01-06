import os
import tempfile
from dataclasses import replace

import aiosqlite
import pytest

import src.models.database as database
import src.db_utils as db_utils
import src.services.channel_service as channel_service
from src.config import config as base_config

# Mock environment before importing
os.environ["BOT_TOKEN"] = "test_token"
os.environ["ADMIN_IDS"] = "123456"


class TestChannelServiceDB:
    @pytest.fixture
    async def temp_db(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        async with aiosqlite.connect(path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=5000")
            await db.execute("""
                CREATE TABLE channels (
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
            await db.execute("CREATE INDEX idx_channels_status ON channels(status)")
            await db.execute("CREATE INDEX idx_channels_category ON channels(category)")
            await db.commit()
        yield path
        os.unlink(path)

    @pytest.mark.asyncio
    async def test_db_connection(self, temp_db):
        async with aiosqlite.connect(temp_db) as db:
            cursor = await db.execute("SELECT 1")
            row = await cursor.fetchone()
            assert row[0] == 1

    @pytest.mark.asyncio
    async def test_insert_channel(self, temp_db):
        async with aiosqlite.connect(temp_db) as db:
            await db.execute(
                "INSERT INTO channels (chat_id, title, username, member_count, submitted_by) "
                "VALUES (?, ?, ?, ?, ?)",
                ("-100123", "Test Channel", "testchan", 1000, 12345)
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM channels WHERE chat_id = ?", ("-100123",))
            row = await cursor.fetchone()
            assert row is not None

    @pytest.mark.asyncio
    async def test_count_queries(self, temp_db):
        async with aiosqlite.connect(temp_db) as db:
            await db.execute(
                "INSERT INTO channels (chat_id, title, submitted_by, status) VALUES (?, ?, ?, ?)",
                ("-100001", "Ch1", 1, "pending")
            )
            await db.execute(
                "INSERT INTO channels (chat_id, title, submitted_by, status) VALUES (?, ?, ?, ?)",
                ("-100002", "Ch2", 1, "approved")
            )
            await db.commit()

            cursor = await db.execute("SELECT COUNT(*) FROM channels WHERE status = 'pending'")
            row = await cursor.fetchone()
            assert row[0] == 1

            cursor = await db.execute("SELECT COUNT(*) FROM channels WHERE status = 'approved'")
            row = await cursor.fetchone()
            assert row[0] == 1

    @pytest.mark.asyncio
    async def test_pagination_query(self, temp_db):
        """测试分页查询"""
        async with aiosqlite.connect(temp_db) as db:
            # 插入 12 条待审核记录
            for i in range(12):
                await db.execute(
                    "INSERT INTO channels (chat_id, title, submitted_by, status) "
                    "VALUES (?, ?, ?, ?)",
                    (f"-10000{i}", f"Channel{i}", 1, "pending")
                )
            await db.commit()

            # 测试第一页 (5条)
            cursor = await db.execute(
                "SELECT * FROM channels WHERE status = 'pending' "
                "ORDER BY submitted_at LIMIT 5 OFFSET 0"
            )
            rows = await cursor.fetchall()
            assert len(rows) == 5

            # 测试第二页
            cursor = await db.execute(
                "SELECT * FROM channels WHERE status = 'pending' "
                "ORDER BY submitted_at LIMIT 5 OFFSET 5"
            )
            rows = await cursor.fetchall()
            assert len(rows) == 5

            # 测试第三页 (只有2条)
            cursor = await db.execute(
                "SELECT * FROM channels WHERE status = 'pending' "
                "ORDER BY submitted_at LIMIT 5 OFFSET 10"
            )
            rows = await cursor.fetchall()
            assert len(rows) == 2


class TestChannelServiceMethods:
    @pytest.fixture
    def patched_db(self, tmp_path, monkeypatch):
        db_path = tmp_path / "data" / "bot.db"
        cfg = replace(base_config, database_path=str(db_path))
        monkeypatch.setattr(database, "config", cfg)
        monkeypatch.setattr(db_utils, "config", cfg)
        return str(db_path)

    @pytest.fixture
    async def init_db(self, patched_db):
        await database.init_db()
        return patched_db

    @pytest.mark.asyncio
    async def test_add_channel_and_exists(self, init_db):
        channel_id = await channel_service.ChannelService.add_channel(
            chat_id="-100100",
            title="Test Channel",
            username="testchan",
            member_count=1000,
            submitted_by=1,
        )
        assert channel_id is not None
        assert await channel_service.ChannelService.channel_exists("-100100") is True

        duplicate = await channel_service.ChannelService.add_channel(
            chat_id="-100100",
            title="Test Channel",
            username="testchan",
            member_count=1000,
            submitted_by=1,
        )
        assert duplicate is None

    @pytest.mark.asyncio
    async def test_approve_reject_counts(self, init_db):
        cid1 = await channel_service.ChannelService.add_channel(
            chat_id="-100200",
            title="Pending Channel",
            username="pending",
            member_count=800,
            submitted_by=2,
        )
        cid2 = await channel_service.ChannelService.add_channel(
            chat_id="-100201",
            title="Another Channel",
            username="another",
            member_count=900,
            submitted_by=3,
        )
        assert cid1 and cid2

        pending_count = await channel_service.ChannelService.get_pending_count()
        assert pending_count == 2

        ok = await channel_service.ChannelService.approve_channel(
            cid1, approved_by=99, category="科技数码"
        )
        assert ok is True

        approved = await channel_service.ChannelService.get_approved_channels()
        assert len(approved) == 1
        assert approved[0]["status"] == "approved"

        rejected = await channel_service.ChannelService.reject_channel(cid2)
        assert rejected is True

        pending_count = await channel_service.ChannelService.get_pending_count()
        approved_count = await channel_service.ChannelService.get_approved_count()
        assert pending_count == 0
        assert approved_count == 1

    @pytest.mark.asyncio
    async def test_pending_pagination(self, init_db):
        for i in range(7):
            await channel_service.ChannelService.add_channel(
                chat_id=f"-10030{i}",
                title=f"Chan{i}",
                username=f"u{i}",
                member_count=700 + i,
                submitted_by=1,
            )

        page0, total0 = await channel_service.ChannelService.get_pending_channels_paginated(
            page=0, per_page=5
        )
        page1, total1 = await channel_service.ChannelService.get_pending_channels_paginated(
            page=1, per_page=5
        )

        assert total0 == 7
        assert total1 == 7
        assert len(page0) == 5
        assert len(page1) == 2

    @pytest.mark.asyncio
    async def test_mark_inactive(self, init_db):
        cid = await channel_service.ChannelService.add_channel(
            chat_id="-100400",
            title="Inactive Channel",
            username="inactive",
            member_count=900,
            submitted_by=1,
        )
        assert cid is not None
        ok = await channel_service.ChannelService.mark_inactive(-100400)
        assert ok is True
        channel = await channel_service.ChannelService.get_channel_by_id(cid)
        assert channel["status"] == "inactive"

    @pytest.mark.asyncio
    async def test_get_pending_channels(self, init_db):
        await channel_service.ChannelService.add_channel(
            chat_id="-100500",
            title="Pending Channel",
            username="pending",
            member_count=700,
            submitted_by=1,
        )
        pending = await channel_service.ChannelService.get_pending_channels()
        assert len(pending) == 1
        assert pending[0]["status"] == "pending"
