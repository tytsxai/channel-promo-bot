from src.utils import LineChunker, escape_markdown


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
        assert escape_markdown(r"path\\to") == r"path\\\\to"

    def test_mixed_content(self):
        result = escape_markdown("Test_Channel (Official)")
        assert r"\_" in result
        assert r"\(" in result
        assert r"\)" in result


class TestLineChunker:
    def test_simple_chunking(self):
        chunker = LineChunker(limit=10)
        out = []
        out.extend(chunker.add_line("12345"))
        out.extend(chunker.add_line("67890"))
        out.extend(chunker.add_line("abc"))
        out.extend(chunker.flush())
        assert out == ["12345", "67890\nabc"]

    def test_long_line_split(self):
        chunker = LineChunker(limit=10)
        out = []
        out.extend(chunker.add_line("12345678901"))
        out.extend(chunker.flush())
        assert out == ["1234567890", "1"]
