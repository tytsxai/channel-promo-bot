import pytest
from src.services.promo_service import _build_promo_text
from src.utils import escape_markdown


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
