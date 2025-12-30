import pytest

from src.config import config
from src.handlers import admin_handlers
from src.handlers.admin_handlers import PENDING_PER_PAGE, is_admin


class TestAdminHandlers:
    def test_is_admin_true(self):
        admin_id = config.admin_ids[0]
        assert is_admin(admin_id) is True

    def test_is_admin_false(self):
        assert is_admin(999999999) is False

    def test_pending_per_page_constant(self):
        assert PENDING_PER_PAGE == 5

    def test_pagination_calculation(self):
        """测试分页计算逻辑"""
        per_page = PENDING_PER_PAGE

        # 12条记录应该有3页
        total = 12
        total_pages = (total + per_page - 1) // per_page
        assert total_pages == 3

        # 5条记录应该有1页
        total = 5
        total_pages = (total + per_page - 1) // per_page
        assert total_pages == 1

        # 0条记录应该有0页
        total = 0
        total_pages = (total + per_page - 1) // per_page
        assert total_pages == 0


class DummyUser:
    def __init__(self, user_id: int):
        self.id = user_id


class DummyMessage:
    def __init__(self, user_id: int = 1):
        self.from_user = DummyUser(user_id)
        self.answers = []
        self.edits = []

    async def answer(self, text: str, reply_markup=None, parse_mode=None):
        self.answers.append(
            {"text": text, "reply_markup": reply_markup, "parse_mode": parse_mode}
        )

    async def edit_text(self, text: str, reply_markup=None, parse_mode=None):
        self.edits.append(
            {"text": text, "reply_markup": reply_markup, "parse_mode": parse_mode}
        )


class DummyCallback:
    def __init__(self, data: str, user_id: int = 1):
        self.data = data
        self.from_user = DummyUser(user_id)
        self.message = DummyMessage(user_id)
        self.answer_calls = []

    async def answer(self, text: str | None = None, show_alert: bool = False):
        self.answer_calls.append({"text": text, "show_alert": show_alert})


@pytest.mark.asyncio
async def test_show_pending_page_empty_for_message(monkeypatch):
    async def fake_get_pending(page: int, per_page: int):
        return [], 0

    monkeypatch.setattr(
        admin_handlers.ChannelService,
        "get_pending_channels_paginated",
        fake_get_pending,
    )

    msg = DummyMessage()
    await admin_handlers._show_pending_page(msg, page=0)
    assert msg.answers
    assert msg.answers[0]["text"] == "📭 暂无待审核的频道"


@pytest.mark.asyncio
async def test_show_pending_page_empty_for_callback(monkeypatch):
    async def fake_get_pending(page: int, per_page: int):
        return [], 0

    monkeypatch.setattr(
        admin_handlers.ChannelService,
        "get_pending_channels_paginated",
        fake_get_pending,
    )
    monkeypatch.setattr(admin_handlers, "CallbackQuery", DummyCallback)

    cb = DummyCallback(data="pending_page:0")
    await admin_handlers._show_pending_page(cb, page=0)
    assert cb.message.edits
    assert cb.message.edits[0]["text"] == "📭 暂无待审核的频道"
    assert cb.answer_calls


@pytest.mark.asyncio
async def test_show_pending_page_with_data(monkeypatch):
    async def fake_get_pending(page: int, per_page: int):
        return (
            [
                {
                    "id": 1,
                    "title": "Test_Channel",
                    "username": "user_name",
                    "member_count": 1234,
                }
            ],
            7,
        )

    monkeypatch.setattr(
        admin_handlers.ChannelService,
        "get_pending_channels_paginated",
        fake_get_pending,
    )

    msg = DummyMessage()
    await admin_handlers._show_pending_page(msg, page=1)
    text = msg.answers[0]["text"]
    assert "Test\\_Channel" in text
    assert "@user\\_name" in text
    assert "第 2/2 页" in text


@pytest.mark.asyncio
async def test_show_pending_page_with_data_callback(monkeypatch):
    async def fake_get_pending(page: int, per_page: int):
        return (
            [
                {
                    "id": 1,
                    "title": "Test_Channel",
                    "username": "user_name",
                    "member_count": 1234,
                }
            ],
            1,
        )

    monkeypatch.setattr(
        admin_handlers.ChannelService,
        "get_pending_channels_paginated",
        fake_get_pending,
    )
    monkeypatch.setattr(admin_handlers, "CallbackQuery", DummyCallback)

    cb = DummyCallback(data="pending_page:0")
    await admin_handlers._show_pending_page(cb, page=0)
    assert cb.message.edits
    assert cb.answer_calls


@pytest.mark.asyncio
async def test_cb_approve_flow(monkeypatch):
    async def fake_get_channel_by_id(channel_id: int):
        return {"id": channel_id, "title": "Chan_1"}

    async def fake_approve(channel_id: int, approved_by: int, category: str):
        return True

    async def fake_classify(title: str):
        return "科技数码"

    monkeypatch.setattr(
        admin_handlers.ChannelService, "get_channel_by_id", fake_get_channel_by_id
    )
    monkeypatch.setattr(
        admin_handlers.ChannelService, "approve_channel", fake_approve
    )
    monkeypatch.setattr(admin_handlers, "classify_channel", fake_classify)

    cb = DummyCallback(data="approve:1", user_id=config.admin_ids[0])
    await admin_handlers.cb_approve(cb)
    assert cb.message.edits
    assert "已通过" in cb.message.edits[0]["text"]
    assert cb.answer_calls


@pytest.mark.asyncio
async def test_cb_reject_flow(monkeypatch):
    async def fake_get_channel_by_id(channel_id: int):
        return {"id": channel_id, "title": "Chan_2"}

    async def fake_reject(channel_id: int):
        return True

    monkeypatch.setattr(
        admin_handlers.ChannelService, "get_channel_by_id", fake_get_channel_by_id
    )
    monkeypatch.setattr(
        admin_handlers.ChannelService, "reject_channel", fake_reject
    )

    cb = DummyCallback(data="reject:2", user_id=config.admin_ids[0])
    await admin_handlers.cb_reject(cb)
    assert cb.message.edits
    assert "已拒绝" in cb.message.edits[0]["text"]
    assert cb.answer_calls


@pytest.mark.asyncio
async def test_cmd_stats(monkeypatch):
    async def fake_pending():
        return 3

    async def fake_approved():
        return 7

    monkeypatch.setattr(admin_handlers.ChannelService, "get_pending_count", fake_pending)
    monkeypatch.setattr(admin_handlers.ChannelService, "get_approved_count", fake_approved)

    msg = DummyMessage(user_id=config.admin_ids[0])
    await admin_handlers.cmd_stats(msg)
    assert msg.answers
    assert "已通过: 7" in msg.answers[0]["text"]


@pytest.mark.asyncio
async def test_cmd_pending_non_admin():
    msg = DummyMessage(user_id=999999)
    await admin_handlers.cmd_pending(msg)
    assert msg.answers == []


@pytest.mark.asyncio
async def test_cmd_pending_admin_calls_show(monkeypatch):
    calls = {"count": 0}

    async def fake_show(target, page: int):
        calls["count"] += 1

    monkeypatch.setattr(admin_handlers, "_show_pending_page", fake_show)
    msg = DummyMessage(user_id=config.admin_ids[0])
    await admin_handlers.cmd_pending(msg)
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_show_pending_page_with_nav_buttons(monkeypatch):
    async def fake_get_pending(page: int, per_page: int):
        return (
            [
                {
                    "id": 1,
                    "title": "Chan",
                    "username": "user",
                    "member_count": 10,
                }
            ],
            12,
        )

    monkeypatch.setattr(
        admin_handlers.ChannelService,
        "get_pending_channels_paginated",
        fake_get_pending,
    )

    msg = DummyMessage()
    await admin_handlers._show_pending_page(msg, page=1)
    assert msg.answers
    assert "第 2/3 页" in msg.answers[0]["text"]


@pytest.mark.asyncio
async def test_cb_pending_page_non_admin():
    cb = DummyCallback(data="pending_page:1", user_id=999999)
    await admin_handlers.cb_pending_page(cb)
    assert cb.answer_calls
    assert cb.answer_calls[0]["text"] == "无权限"


@pytest.mark.asyncio
async def test_cb_pending_page_invalid(monkeypatch):
    cb = DummyCallback(data="pending_page:abc", user_id=config.admin_ids[0])
    await admin_handlers.cb_pending_page(cb)
    assert cb.answer_calls
    assert cb.answer_calls[0]["text"] == "操作失败"


@pytest.mark.asyncio
async def test_cb_approve_non_admin():
    cb = DummyCallback(data="approve:1", user_id=999999)
    await admin_handlers.cb_approve(cb)
    assert cb.answer_calls
    assert cb.answer_calls[0]["text"] == "无权限"


@pytest.mark.asyncio
async def test_cb_reject_non_admin():
    cb = DummyCallback(data="reject:1", user_id=999999)
    await admin_handlers.cb_reject(cb)
    assert cb.answer_calls
    assert cb.answer_calls[0]["text"] == "无权限"


@pytest.mark.asyncio
async def test_cb_approve_channel_missing(monkeypatch):
    async def fake_get_channel_by_id(channel_id: int):
        return None

    monkeypatch.setattr(
        admin_handlers.ChannelService, "get_channel_by_id", fake_get_channel_by_id
    )
    cb = DummyCallback(data="approve:99", user_id=config.admin_ids[0])
    await admin_handlers.cb_approve(cb)
    assert cb.answer_calls
    assert cb.answer_calls[0]["text"] == "频道不存在"


@pytest.mark.asyncio
async def test_cb_reject_channel_missing(monkeypatch):
    async def fake_get_channel_by_id(channel_id: int):
        return None

    monkeypatch.setattr(
        admin_handlers.ChannelService, "get_channel_by_id", fake_get_channel_by_id
    )
    cb = DummyCallback(data="reject:99", user_id=config.admin_ids[0])
    await admin_handlers.cb_reject(cb)
    assert cb.answer_calls
    assert cb.answer_calls[0]["text"] == "频道不存在"


@pytest.mark.asyncio
async def test_cb_approve_exception(monkeypatch):
    async def fake_get_channel_by_id(channel_id: int):
        return {"id": channel_id, "title": "Chan_3"}

    async def fake_approve(channel_id: int, approved_by: int, category: str):
        raise RuntimeError("boom")

    async def fake_classify(title: str):
        return "科技数码"

    monkeypatch.setattr(
        admin_handlers.ChannelService, "get_channel_by_id", fake_get_channel_by_id
    )
    monkeypatch.setattr(
        admin_handlers.ChannelService, "approve_channel", fake_approve
    )
    monkeypatch.setattr(admin_handlers, "classify_channel", fake_classify)

    cb = DummyCallback(data="approve:3", user_id=config.admin_ids[0])
    await admin_handlers.cb_approve(cb)
    assert cb.answer_calls
    assert cb.answer_calls[0]["text"] == "操作失败"


@pytest.mark.asyncio
async def test_cb_reject_exception(monkeypatch):
    async def fake_get_channel_by_id(channel_id: int):
        return {"id": channel_id, "title": "Chan_4"}

    async def fake_reject(channel_id: int):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        admin_handlers.ChannelService, "get_channel_by_id", fake_get_channel_by_id
    )
    monkeypatch.setattr(
        admin_handlers.ChannelService, "reject_channel", fake_reject
    )

    cb = DummyCallback(data="reject:4", user_id=config.admin_ids[0])
    await admin_handlers.cb_reject(cb)
    assert cb.answer_calls
    assert cb.answer_calls[0]["text"] == "操作失败"


@pytest.mark.asyncio
async def test_cmd_stats_non_admin():
    msg = DummyMessage(user_id=999999)
    await admin_handlers.cmd_stats(msg)
    assert msg.answers == []


@pytest.mark.asyncio
async def test_cb_pending_page_valid(monkeypatch):
    calls = {"count": 0}

    async def fake_show(target, page: int):
        calls["count"] += 1

    monkeypatch.setattr(admin_handlers, "_show_pending_page", fake_show)
    cb = DummyCallback(data="pending_page:2", user_id=config.admin_ids[0])
    await admin_handlers.cb_pending_page(cb)
    assert calls["count"] == 1
