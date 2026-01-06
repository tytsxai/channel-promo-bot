from src.config import config


def get_database_path(database_path: str | None = None) -> tuple[str, bool]:
    """Return SQLite path and whether it should be opened as URI."""
    path = database_path or config.database_path
    if path == ":memory:":
        return "file:shared_mem_db?mode=memory&cache=shared", True
    return path, False
