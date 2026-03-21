"""Tests for src/db_utils.py – targets 80%+ coverage."""
from dataclasses import replace

import src.db_utils as db_utils
from src.config import config as base_config


class TestGetDatabasePath:
    def test_memory_returns_uri(self):
        path, use_uri = db_utils.get_database_path(":memory:")
        assert use_uri is True
        assert "mode=memory" in path
        assert "cache=shared" in path

    def test_file_path_not_uri(self, tmp_path):
        db_file = str(tmp_path / "bot.db")
        path, use_uri = db_utils.get_database_path(db_file)
        assert use_uri is False
        assert path == db_file

    def test_uses_config_when_no_arg(self, monkeypatch):
        cfg = replace(base_config, database_path=":memory:")
        monkeypatch.setattr(db_utils, "config", cfg)
        path, use_uri = db_utils.get_database_path()
        assert use_uri is True

    def test_uses_config_file_path(self, tmp_path, monkeypatch):
        db_file = str(tmp_path / "cfg.db")
        cfg = replace(base_config, database_path=db_file)
        monkeypatch.setattr(db_utils, "config", cfg)
        path, use_uri = db_utils.get_database_path()
        assert use_uri is False
        assert path == db_file

    def test_explicit_arg_overrides_config(self, monkeypatch):
        cfg = replace(base_config, database_path=":memory:")
        monkeypatch.setattr(db_utils, "config", cfg)
        path, use_uri = db_utils.get_database_path("/tmp/override.db")
        assert use_uri is False
        assert path == "/tmp/override.db"

    def test_memory_uri_format(self):
        path, _ = db_utils.get_database_path(":memory:")
        assert path.startswith("file:")
        assert "shared_mem_db" in path
