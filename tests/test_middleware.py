import time

import pytest

import src.middleware as middleware
from src.middleware import RateLimitMiddleware


class TestRateLimitMiddleware:
    def test_init_defaults(self):
        middleware = RateLimitMiddleware()
        assert middleware.limit == 5
        assert middleware.window == 60
        assert middleware.cleanup_interval == 300

    def test_init_custom(self):
        middleware = RateLimitMiddleware(limit=10, window=30, cleanup_interval=100)
        assert middleware.limit == 10
        assert middleware.window == 30
        assert middleware.cleanup_interval == 100

    def test_requests_tracking(self):
        middleware = RateLimitMiddleware(limit=3, window=60)
        user_id = 12345
        now = time.time()

        middleware.requests[user_id] = [now - 10, now - 5]
        assert len(middleware.requests[user_id]) == 2

    def test_cleanup_stale_entries_skips_when_interval_not_reached(self):
        middleware = RateLimitMiddleware(limit=3, window=60, cleanup_interval=300)
        now = time.time()
        middleware._last_cleanup = now - 100  # 100秒前清理过
        middleware.requests[111] = [now - 1000]  # 过期记录

        middleware._cleanup_stale_entries(now)
        # 未到清理间隔，不应清理
        assert 111 in middleware.requests

    def test_cleanup_stale_entries_removes_expired(self):
        middleware = RateLimitMiddleware(limit=3, window=60, cleanup_interval=300)
        now = time.time()
        middleware._last_cleanup = now - 400  # 超过清理间隔

        middleware.requests[111] = [now - 1000]  # 过期
        middleware.requests[222] = [now - 10]    # 未过期
        middleware.requests[333] = []            # 空列表

        middleware._cleanup_stale_entries(now)

        assert 111 not in middleware.requests
        assert 222 in middleware.requests
        assert 333 not in middleware.requests


class DummyUser:
    def __init__(self, user_id: int):
        self.id = user_id


class DummyMessage:
    def __init__(self, user_id: int | None = 1):
        self.from_user = DummyUser(user_id) if user_id is not None else None
        self.answers = []

    async def answer(self, text: str):
        self.answers.append(text)


@pytest.mark.asyncio
async def test_call_non_message_calls_handler():
    mw = RateLimitMiddleware()
    calls = {"count": 0}

    async def handler(event, data):
        calls["count"] += 1
        return "ok"

    result = await mw(handler, event="not-message", data={})
    assert result == "ok"
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_call_message_no_user_calls_handler(monkeypatch):
    monkeypatch.setattr(middleware, "Message", DummyMessage)
    mw = RateLimitMiddleware()
    calls = {"count": 0}

    async def handler(event, data):
        calls["count"] += 1
        return "ok"

    event = DummyMessage(user_id=None)
    result = await mw(handler, event=event, data={})
    assert result == "ok"
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_call_rate_limited(monkeypatch):
    monkeypatch.setattr(middleware, "Message", DummyMessage)
    mw = RateLimitMiddleware(limit=1, window=60)
    user_id = 42
    now = time.time()
    mw.requests[user_id] = [now - 1]

    calls = {"count": 0}

    async def handler(event, data):
        calls["count"] += 1
        return "ok"

    event = DummyMessage(user_id=user_id)
    result = await mw(handler, event=event, data={})
    assert result is None
    assert calls["count"] == 0
    assert event.answers


@pytest.mark.asyncio
async def test_call_allows_request(monkeypatch):
    monkeypatch.setattr(middleware, "Message", DummyMessage)
    mw = RateLimitMiddleware(limit=2, window=60)
    calls = {"count": 0}

    async def handler(event, data):
        calls["count"] += 1
        return "ok"

    event = DummyMessage(user_id=99)
    result = await mw(handler, event=event, data={})
    assert result == "ok"
    assert calls["count"] == 1
