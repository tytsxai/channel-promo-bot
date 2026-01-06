import re

MARKDOWN_SPECIAL_CHARS = r'[\\_*\[\]()~`>#+=|{}.!-]'


def escape_markdown(text: str | None) -> str:
    """Escape special characters for Telegram MarkdownV2.

    任何动态内容（标题、分类、用户名、URL 片段等）在 MarkdownV2 下都必须先转义。
    HTML parse_mode 请使用 html.escape。
    """
    if not text:
        return ""
    return re.sub(MARKDOWN_SPECIAL_CHARS, r"\\\g<0>", text)


class LineChunker:
    """Build message chunks incrementally to stay within a size limit."""

    def __init__(self, limit: int):
        self.limit = limit
        self._buffer: list[str] = []
        self._length = 0

    def add_line(self, line: str) -> list[str]:
        messages: list[str] = []
        if len(line) > self.limit:
            messages.extend(self.flush())
            for i in range(0, len(line), self.limit):
                messages.append(line[i : i + self.limit])
            return messages

        extra = len(line) + (1 if self._buffer else 0)
        if self._length + extra > self.limit:
            messages.extend(self.flush())

        was_empty = not self._buffer
        self._buffer.append(line)
        self._length += len(line) if was_empty else len(line) + 1
        return messages

    def flush(self) -> list[str]:
        if not self._buffer:
            return []
        message = "\n".join(self._buffer)
        self._buffer = []
        self._length = 0
        return [message]


def chunk_lines(lines: list[str], limit: int) -> list[str]:
    """Chunk lines into messages that stay within the character limit."""
    chunker = LineChunker(limit)
    messages: list[str] = []
    for line in lines:
        messages.extend(chunker.add_line(line))
    messages.extend(chunker.flush())
    return messages
