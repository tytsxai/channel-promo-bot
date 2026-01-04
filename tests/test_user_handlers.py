import pytest

from src.config import config
from src.handlers import user_handlers
from src.handlers.user_handlers import _extract_username, get_help_text


class TestExtractUsername:
    def test_at_username(self):
        assert _extract_username("@testchannel") == "testchannel"

    def test_https_link(self):
        assert _extract_username("https://t.me/testchannel") == "testchannel"

    def test_short_link(self):
        assert _extract_username("t.me/testchannel") == "testchannel"

    def test_plain_username(self):
        assert _extract_username("testchannel") == "testchannel"

    def test_link_inside_text(self):
        text = "Heisenberg, [2:32 AM]\\nhttps://t.me/moyingnet"
        assert _extract_username(text) == "moyingnet"

    def test_invalid_short(self):
        assert _extract_username("ab") is None

    def test_invalid_start_number(self):
        assert _extract_username("123channel") is None

    def test_with_trailing_path(self):
        result = _extract_username("https://t.me/channel_name")
        assert result == "channel_name"

    def test_with_query_params(self):
        result = _extract_username("https://t.me/channel_name?start=abc")
        assert result == "channel_name"

    def test_invalid_domain(self):
        assert _extract_username("https://example.com/channel") is None


class TestGetHelpText:
    def test_help_text_contains_commands(self):
        text = get_help_text()
        assert "/start" in text
        assert "/submit" in text
        assert "/list" in text

    def test_help_text_contains_min_members(self):
        text = get_help_text()
        assert str(config.min_members) in text


class DummyUser:
    def __init__(self, user_id: int, username: str | None = None):
        self.id = user_id
        self.username = username


class DummyMessage:
    def __init__(self, user_id: int = 1):
        self.from_user = DummyUser(user_id)
        self.answers = []

    async def answer(self, text: str, reply_markup=None, parse_mode=None):
        self.answers.append(
            {"text": text, "reply_markup": reply_markup, "parse_mode": parse_mode}
        )


class DummyCommand:
    def __init__(self, args: str | None):
        self.args = args


class DummyChat:
    def __init__(self, chat_id: int, title: str, chat_type: str = "channel"):
        self.id = chat_id
        self.title = title
        self.type = chat_type


class DummyMember:
    def __init__(self, status: str):
        self.status = status


class DummyBot:
    def __init__(
        self,
        member_status: str = "administrator",
        bot_status: str = "administrator",
        member_count: int = 800,
        chat_type: str = "channel",
        raise_on_chat: bool = False,
        raise_on_member: bool = False,
        raise_on_count: bool = False,
    ):
        self.member_status = member_status
        self.bot_status = bot_status
        self.member_count = member_count
        self.chat_type = chat_type
        self.raise_on_chat = raise_on_chat
        self.raise_on_member = raise_on_member
        self.raise_on_count = raise_on_count
        self.bot_id = 999

    async def get_chat(self, username: str):
        if self.raise_on_chat:
            raise RuntimeError("chat error")
        return DummyChat(chat_id=-100123, title="Test_Channel", chat_type=self.chat_type)

    async def get_chat_member(self, chat_id: int, user_id: int):
        if self.raise_on_member and user_id != self.bot_id:
            raise RuntimeError("member error")
        status = self.bot_status if user_id == self.bot_id else self.member_status
        return DummyMember(status=status)

    async def get_chat_member_count(self, chat_id: int):
        if self.raise_on_count:
            raise RuntimeError("count error")
        return self.member_count

    async def get_me(self):
        return DummyUser(self.bot_id, username="test_bot")


@pytest.mark.asyncio
async def test_cmd_submit_missing_args():
    msg = DummyMessage()
    cmd = DummyCommand(args=None)
    bot = DummyBot()
    await user_handlers.cmd_submit(msg, cmd, bot)
    assert "请直接发送频道链接" in msg.answers[0]["text"]


@pytest.mark.asyncio
async def test_cmd_start_and_help():
    msg = DummyMessage()
    bot = DummyBot()
    await user_handlers.cmd_start(msg, bot)
    assert "欢迎使用互推机器人" in msg.answers[0]["text"]

    msg = DummyMessage()
    await user_handlers.cmd_help(msg, bot)
    assert "/submit" in msg.answers[0]["text"]
    assert msg.answers[0]["parse_mode"] == "Markdown"


@pytest.mark.asyncio
async def test_cmd_submit_invalid_link():
    msg = DummyMessage()
    cmd = DummyCommand(args="ab")
    bot = DummyBot()
    await user_handlers.cmd_submit(msg, cmd, bot)
    assert "无法识别频道链接" in msg.answers[0]["text"]


@pytest.mark.asyncio
async def test_cmd_submit_get_chat_failure():
    msg = DummyMessage()
    cmd = DummyCommand(args="@testchannel")
    bot = DummyBot(raise_on_chat=True)
    await user_handlers.cmd_submit(msg, cmd, bot)
    assert "无法获取频道" in msg.answers[0]["text"]


@pytest.mark.asyncio
async def test_cmd_submit_get_chat_member_failure(monkeypatch):
    async def fake_exists(chat_id: str):
        return False

    monkeypatch.setattr(user_handlers.ChannelService, "channel_exists", fake_exists)
    msg = DummyMessage()
    cmd = DummyCommand(args="@testchannel")
    bot = DummyBot(raise_on_member=True)
    await user_handlers.cmd_submit(msg, cmd, bot)
    assert "无法验证你的管理员身份" in msg.answers[0]["text"]


@pytest.mark.asyncio
async def test_cmd_submit_get_member_count_failure(monkeypatch):
    async def fake_exists(chat_id: str):
        return False

    monkeypatch.setattr(user_handlers.ChannelService, "channel_exists", fake_exists)
    msg = DummyMessage()
    cmd = DummyCommand(args="@testchannel")
    bot = DummyBot(raise_on_count=True)
    await user_handlers.cmd_submit(msg, cmd, bot)
    assert "无法获取频道成员数" in msg.answers[0]["text"]


@pytest.mark.asyncio
async def test_cmd_submit_rejects_non_channel(monkeypatch):
    async def fake_exists(chat_id: str):
        return False

    monkeypatch.setattr(user_handlers.ChannelService, "channel_exists", fake_exists)
    msg = DummyMessage()
    cmd = DummyCommand(args="@testchannel")
    bot = DummyBot(chat_type="group")
    await user_handlers.cmd_submit(msg, cmd, bot)
    assert "不是频道" in msg.answers[0]["text"]


@pytest.mark.asyncio
async def test_cmd_submit_non_admin(monkeypatch):
    async def fake_exists(chat_id: str):
        return False

    async def fake_add(**kwargs):
        raise AssertionError("should not add when not admin")

    monkeypatch.setattr(user_handlers.ChannelService, "channel_exists", fake_exists)
    monkeypatch.setattr(user_handlers.ChannelService, "add_channel", fake_add)

    msg = DummyMessage()
    cmd = DummyCommand(args="@testchannel")
    bot = DummyBot(member_status="member")
    await user_handlers.cmd_submit(msg, cmd, bot)
    assert "仅频道管理员可以提交" in msg.answers[0]["text"]


@pytest.mark.asyncio
async def test_cmd_submit_member_count_too_low(monkeypatch):
    async def fake_exists(chat_id: str):
        return False

    monkeypatch.setattr(user_handlers.ChannelService, "channel_exists", fake_exists)

    msg = DummyMessage()
    cmd = DummyCommand(args="@testchannel")
    bot = DummyBot(member_status="administrator", member_count=10)
    await user_handlers.cmd_submit(msg, cmd, bot)
    assert "成员数" in msg.answers[0]["text"]


@pytest.mark.asyncio
async def test_cmd_submit_duplicate(monkeypatch):
    async def fake_exists(chat_id: str):
        return True

    async def fake_add(**kwargs):
        raise AssertionError("should not add when duplicate")

    monkeypatch.setattr(user_handlers.ChannelService, "channel_exists", fake_exists)
    monkeypatch.setattr(user_handlers.ChannelService, "add_channel", fake_add)

    msg = DummyMessage()
    cmd = DummyCommand(args="@testchannel")
    bot = DummyBot()
    await user_handlers.cmd_submit(msg, cmd, bot)
    assert "已提交过" in msg.answers[0]["text"]


@pytest.mark.asyncio
async def test_cmd_submit_duplicate_on_insert(monkeypatch):
    async def fake_exists(chat_id: str):
        return False

    async def fake_add(**kwargs):
        return None

    monkeypatch.setattr(user_handlers.ChannelService, "channel_exists", fake_exists)
    monkeypatch.setattr(user_handlers.ChannelService, "add_channel", fake_add)

    msg = DummyMessage()
    cmd = DummyCommand(args="@testchannel")
    bot = DummyBot()
    await user_handlers.cmd_submit(msg, cmd, bot)
    assert "已提交过" in msg.answers[0]["text"]


@pytest.mark.asyncio
async def test_cmd_submit_success(monkeypatch):
    calls = {"added": False}

    async def fake_exists(chat_id: str):
        return False

    async def fake_add(**kwargs):
        calls["added"] = True
        return 1

    monkeypatch.setattr(user_handlers.ChannelService, "channel_exists", fake_exists)
    monkeypatch.setattr(user_handlers.ChannelService, "add_channel", fake_add)

    msg = DummyMessage()
    cmd = DummyCommand(args="@testchannel")
    bot = DummyBot()
    await user_handlers.cmd_submit(msg, cmd, bot)
    assert calls["added"] is True
    assert "频道提交成功" in msg.answers[0]["text"]


@pytest.mark.asyncio
async def test_cmd_submit_database_error(monkeypatch):
    async def fake_exists(chat_id: str):
        return False

    async def fake_add(**kwargs):
        raise RuntimeError("db error")

    monkeypatch.setattr(user_handlers.ChannelService, "channel_exists", fake_exists)
    monkeypatch.setattr(user_handlers.ChannelService, "add_channel", fake_add)

    msg = DummyMessage()
    cmd = DummyCommand(args="@testchannel")
    bot = DummyBot()
    await user_handlers.cmd_submit(msg, cmd, bot)
    assert "系统错误" in msg.answers[0]["text"]


@pytest.mark.asyncio
async def test_cmd_list_with_channels(monkeypatch):
    async def fake_get_channels():
        return [
            {
                "title": "Chan_1",
                "username": "user_name",
                "category": "科技数码",
            }
        ]

    monkeypatch.setattr(
        user_handlers.ChannelService, "get_approved_channels", fake_get_channels
    )

    msg = DummyMessage()
    await user_handlers.cmd_list(msg)
    text = msg.answers[0]["text"]
    assert "Chan\\_1" in text
    assert "@user\\_name" in text


@pytest.mark.asyncio
async def test_cmd_list_empty(monkeypatch):
    async def fake_get_channels():
        return []

    monkeypatch.setattr(
        user_handlers.ChannelService, "get_approved_channels", fake_get_channels
    )

    msg = DummyMessage()
    await user_handlers.cmd_list(msg)
    assert "暂无已审核通过的频道" in msg.answers[0]["text"]


@pytest.mark.asyncio
async def test_cmd_list_error(monkeypatch):
    async def fake_get_channels():
        raise RuntimeError("db error")

    monkeypatch.setattr(
        user_handlers.ChannelService, "get_approved_channels", fake_get_channels
    )

    msg = DummyMessage()
    await user_handlers.cmd_list(msg)
    assert "获取频道列表失败" in msg.answers[0]["text"]
