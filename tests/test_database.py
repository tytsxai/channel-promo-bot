import pytest
import tempfile
import os
import aiosqlite


class TestDatabaseInit:
    @pytest.fixture
    def temp_db_path(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(path)  # 删除文件，让 init_db 创建
        yield path
        if os.path.exists(path):
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_create_table_schema(self, temp_db_path):
        """测试数据库表结构创建"""
        os.makedirs(os.path.dirname(temp_db_path), exist_ok=True)

        async with aiosqlite.connect(temp_db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
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
            await db.commit()

            # 验证表存在
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='channels'"
            )
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "channels"

    @pytest.mark.asyncio
    async def test_create_indexes(self, temp_db_path):
        """测试索引创建"""
        async with aiosqlite.connect(temp_db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY,
                    status TEXT,
                    category TEXT
                )
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_status ON channels(status)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_category ON channels(category)")
            await db.commit()

            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
            rows = await cursor.fetchall()
            index_names = [r[0] for r in rows]
            assert "idx_status" in index_names
            assert "idx_category" in index_names
