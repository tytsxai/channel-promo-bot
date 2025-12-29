import pytest
import tempfile
import os
import aiosqlite
import sys

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
                "INSERT INTO channels (chat_id, title, username, member_count, submitted_by) VALUES (?, ?, ?, ?, ?)",
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
                    "INSERT INTO channels (chat_id, title, submitted_by, status) VALUES (?, ?, ?, ?)",
                    (f"-10000{i}", f"Channel{i}", 1, "pending")
                )
            await db.commit()

            # 测试第一页 (5条)
            cursor = await db.execute(
                "SELECT * FROM channels WHERE status = 'pending' ORDER BY submitted_at LIMIT 5 OFFSET 0"
            )
            rows = await cursor.fetchall()
            assert len(rows) == 5

            # 测试第二页
            cursor = await db.execute(
                "SELECT * FROM channels WHERE status = 'pending' ORDER BY submitted_at LIMIT 5 OFFSET 5"
            )
            rows = await cursor.fetchall()
            assert len(rows) == 5

            # 测试第三页 (只有2条)
            cursor = await db.execute(
                "SELECT * FROM channels WHERE status = 'pending' ORDER BY submitted_at LIMIT 5 OFFSET 10"
            )
            rows = await cursor.fetchall()
            assert len(rows) == 2
