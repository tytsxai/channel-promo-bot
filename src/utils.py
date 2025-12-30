import re

MARKDOWN_SPECIAL_CHARS = r'[\\_*\[\]()~`>#+=|{}.!-]'


def escape_markdown(text: str | None) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    if not text:
        return ""
    return re.sub(MARKDOWN_SPECIAL_CHARS, r"\\\g<0>", text)
