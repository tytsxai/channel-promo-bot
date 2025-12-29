import pytest
from src.utils import escape_markdown


class TestEscapeMarkdown:
    def test_empty_string(self):
        assert escape_markdown("") == ""

    def test_none_like(self):
        assert escape_markdown("") == ""

    def test_plain_text(self):
        assert escape_markdown("Hello World") == "Hello World"

    def test_special_chars(self):
        assert escape_markdown("Hello_World") == r"Hello\_World"
        assert escape_markdown("*bold*") == r"\*bold\*"
        assert escape_markdown("[link]") == r"\[link\]"

    def test_mixed_content(self):
        result = escape_markdown("Test_Channel (Official)")
        assert r"\_" in result
        assert r"\(" in result
        assert r"\)" in result
