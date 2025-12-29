import pytest
from src.handlers.user_handlers import _extract_username, get_help_text
from src.config import config


class TestExtractUsername:
    def test_at_username(self):
        assert _extract_username("@testchannel") == "testchannel"

    def test_https_link(self):
        assert _extract_username("https://t.me/testchannel") == "testchannel"

    def test_short_link(self):
        assert _extract_username("t.me/testchannel") == "testchannel"

    def test_plain_username(self):
        assert _extract_username("testchannel") == "testchannel"

    def test_invalid_short(self):
        assert _extract_username("ab") is None

    def test_invalid_start_number(self):
        assert _extract_username("123channel") is None

    def test_with_trailing_path(self):
        result = _extract_username("https://t.me/channel_name")
        assert result == "channel_name"


class TestGetHelpText:
    def test_help_text_contains_commands(self):
        text = get_help_text()
        assert "/start" in text
        assert "/submit" in text
        assert "/list" in text

    def test_help_text_contains_min_members(self):
        text = get_help_text()
        assert str(config.min_members) in text
