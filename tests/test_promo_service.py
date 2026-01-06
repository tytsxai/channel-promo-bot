import pytest

import src.services.promo_service as promo_service
from src.services.promo_service import (
    MAX_MESSAGE_LEN,
    _build_promo_messages,
    _build_promo_text,
    _chunk_lines,
)


class TestBuildPromoText:
    def test_empty_channels(self):
        result = _build_promo_text([])
        assert "今日互推精选" in result

    def test_single_channel(self):
        channels = [{
            "title": "Test Channel",
            "username": "testchannel",
            "category": "科技数码"
        }]
        result = _build_promo_text(channels)
        assert "科技数码" in result
        assert "testchannel" in result

    def test_channel_without_username(self):
        channels = [{
            "title": "Private Channel",
            "username": None,
            "category": "其他"
        }]
        result = _build_promo_text(channels)
        assert "Private Channel" in result

    def test_multiple_categories(self):
        channels = [
            {"title": "Tech", "username": "tech", "category": "科技数码"},
            {"title": "Game", "username": "game", "category": "游戏电竞"},
        ]
        result = _build_promo_text(channels)
        assert "科技数码" in result
        assert "游戏电竞" in result

    def test_footer_present(self):
        result = _build_promo_text([])
        assert "/help" in result

    def test_special_chars_escaped(self):
        channels = [{
            "title": "Test_Channel",
            "username": "test",
            "category": "其他"
        }]
        result = _build_promo_text(channels)
        assert r"\_" in result

    def test_username_escaped_in_url(self):
        channels = [{
            "title": "Channel",
            "username": "test_channel",
            "category": "其他"
        }]
        result = _build_promo_text(channels)
        assert "https://t.me/test\\_channel" in result

    def test_chunk_lines_respects_limit(self):
        lines = ["12345", "67890", "abc"]
        chunks = _chunk_lines(lines, limit=10)
        assert chunks == ["12345", "67890\nabc"]

    def test_chunk_lines_splits_long_line(self):
        chunks = _chunk_lines(["12345678901"], limit=10)
        assert chunks == ["1234567890", "1"]

    def test_chunk_lines_flushes_buffer_before_long_line(self):
        chunks = _chunk_lines(["abc", "12345678901"], limit=10)
        assert chunks == ["abc", "1234567890", "1"]

    def test_build_promo_messages_chunks(self):
        channels = [
            {
                "title": "T" * 80,
                "username": f"user{i}",
                "category": "其他",
            }
            for i in range(120)
        ]
        messages = _build_promo_messages(channels)
        assert len(messages) > 1
        assert all(len(m) <= MAX_MESSAGE_LEN for m in messages)


class DummyRetryAfter(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after


class DummyForbidden(Exception):
    pass


class DummyNotFound(Exception):
    pass


class DummyBadRequest(Exception):
    pass


class DummyBot:
    def __init__(self, side_effects):
        self.side_effects = list(side_effects)
        self.calls = 0

    async def send_message(self, **kwargs):
        self.calls += 1
        if self.side_effects:
            effect = self.side_effects.pop(0)
            if isinstance(effect, Exception):
                raise effect
        return None


@pytest.mark.asyncio
async def test_send_with_retry_success(monkeypatch):
    bot = DummyBot([None])
    result = await promo_service._send_with_retry(bot, chat_id=1, text="hi")
    assert result is True
    assert bot.calls == 1


@pytest.mark.asyncio
async def test_send_with_retry_rate_limit_then_success(monkeypatch):
    async def no_sleep(_):
        return None

    monkeypatch.setattr(promo_service, "TelegramRetryAfter", DummyRetryAfter)
    monkeypatch.setattr(promo_service.asyncio, "sleep", no_sleep)

    bot = DummyBot([DummyRetryAfter(1), None])
    result = await promo_service._send_with_retry(bot, chat_id=1, text="hi")
    assert result is True
    assert bot.calls == 2


@pytest.mark.asyncio
async def test_send_with_retry_forbidden_marks_inactive(monkeypatch):
    async def no_sleep(_):
        return None

    calls = {"inactive": 0}

    async def mark_inactive(chat_id: int):
        calls["inactive"] += 1
        return True

    monkeypatch.setattr(promo_service, "TelegramForbiddenError", DummyForbidden)
    monkeypatch.setattr(promo_service.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(promo_service.ChannelService, "mark_inactive", mark_inactive)

    bot = DummyBot([DummyForbidden()])
    result = await promo_service._send_with_retry(bot, chat_id=1, text="hi")
    assert result is False
    assert calls["inactive"] == 1


@pytest.mark.asyncio
async def test_send_with_retry_not_found_marks_inactive(monkeypatch):
    async def no_sleep(_):
        return None

    calls = {"inactive": 0}

    async def mark_inactive(chat_id: int):
        calls["inactive"] += 1
        return True

    monkeypatch.setattr(promo_service, "TelegramNotFound", DummyNotFound)
    monkeypatch.setattr(promo_service.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(promo_service.ChannelService, "mark_inactive", mark_inactive)

    bot = DummyBot([DummyNotFound()])
    result = await promo_service._send_with_retry(bot, chat_id=1, text="hi")
    assert result is False
    assert calls["inactive"] == 1


@pytest.mark.asyncio
async def test_send_with_retry_bad_request(monkeypatch):
    monkeypatch.setattr(promo_service, "TelegramBadRequest", DummyBadRequest)
    bot = DummyBot([DummyBadRequest()])
    result = await promo_service._send_with_retry(bot, chat_id=1, text="hi")
    assert result is False


@pytest.mark.asyncio
async def test_send_with_retry_generic_exception_then_success(monkeypatch):
    async def no_sleep(_):
        return None

    monkeypatch.setattr(promo_service.asyncio, "sleep", no_sleep)
    bot = DummyBot([RuntimeError("boom"), None])
    result = await promo_service._send_with_retry(bot, chat_id=1, text="hi")
    assert result is True
    assert bot.calls == 2


@pytest.mark.asyncio
async def test_send_with_retry_generic_exception_exhausts(monkeypatch):
    async def no_sleep(_):
        return None

    monkeypatch.setattr(promo_service.asyncio, "sleep", no_sleep)
    bot = DummyBot([RuntimeError("boom"), RuntimeError("boom"), RuntimeError("boom")])
    result = await promo_service._send_with_retry(
        bot, chat_id=1, text="hi", max_retries=3
    )
    assert result is False


@pytest.mark.asyncio
async def test_send_promo_to_all_no_channels(monkeypatch):
    async def fake_get_count():
        return 0

    monkeypatch.setattr(
        promo_service.ChannelService, "get_approved_count", fake_get_count
    )
    sent, failed = await promo_service.send_promo_to_all(bot=DummyBot([]))
    assert sent == 0
    assert failed == 0


@pytest.mark.asyncio
async def test_send_promo_to_all_counts(monkeypatch):
    async def no_sleep(_):
        return None

    async def fake_get_count():
        return 2

    async def fake_iter(batch_size=500):
        yield {"chat_id": "1", "title": "A", "username": "a", "category": "其他"}
        yield {"chat_id": "2", "title": "B", "username": "b", "category": "其他"}

    messages = ["m1", "m2"]
    calls = {"count": 0}

    async def fake_send(bot, chat_id: int, text: str, limiter=None):
        calls["count"] += 1
        return chat_id != 2

    monkeypatch.setattr(
        promo_service.ChannelService, "get_approved_count", fake_get_count
    )
    monkeypatch.setattr(
        promo_service.ChannelService, "iter_approved_channels", fake_iter
    )
    async def fake_build():
        return messages

    monkeypatch.setattr(promo_service, "_build_promo_messages_from_db", fake_build)
    monkeypatch.setattr(promo_service, "_send_with_retry", fake_send)
    monkeypatch.setattr(promo_service.asyncio, "sleep", no_sleep)

    sent, failed = await promo_service.send_promo_to_all(bot=DummyBot([]))
    assert sent == 1
    assert failed == 1
    assert calls["count"] == 3


@pytest.mark.asyncio
async def test_send_promo_to_all_invalid_chat_id(monkeypatch):
    async def fake_get_count():
        return 1

    async def fake_iter(batch_size=500):
        yield {"chat_id": "bad", "title": "A", "username": "a", "category": "其他"}

    async def fake_send(bot, chat_id: int, text: str, limiter=None):
        raise AssertionError("should not send")

    monkeypatch.setattr(
        promo_service.ChannelService, "get_approved_count", fake_get_count
    )
    monkeypatch.setattr(
        promo_service.ChannelService, "iter_approved_channels", fake_iter
    )
    async def fake_build():
        return ["msg"]

    monkeypatch.setattr(promo_service, "_build_promo_messages_from_db", fake_build)
    monkeypatch.setattr(promo_service, "_send_with_retry", fake_send)

    sent, failed = await promo_service.send_promo_to_all(bot=DummyBot([]))
    assert sent == 0
    assert failed == 1
