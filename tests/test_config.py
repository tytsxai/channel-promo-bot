import pytest

from src.config import Config, ConfigError


class TestConfig:
    def test_promo_hour_default(self):
        from src.config import config
        assert 0 <= config.promo_hour_utc <= 23

    def test_promo_minute_default(self):
        from src.config import config
        assert 0 <= config.promo_minute <= 59

    def test_min_members_default(self):
        from src.config import config
        assert config.min_members == 700

    def test_admin_ids_loaded(self):
        from src.config import config
        assert len(config.admin_ids) > 0

    def test_rate_limit_defaults(self):
        from src.config import config
        assert config.rate_limit == 10
        assert config.rate_limit_window == 60
        assert config.rate_limit_cleanup == 300

    def test_logging_defaults(self):
        from src.config import config
        assert config.log_level == "INFO"
        assert config.log_format == "text"
        assert config.log_file is None

    def test_healthcheck_defaults(self):
        from src.config import config
        assert config.healthcheck_port == 0
        assert config.healthcheck_host == "127.0.0.1"

    def test_from_env_missing_token(self, monkeypatch):
        monkeypatch.delenv("BOT_TOKEN", raising=False)
        monkeypatch.setenv("ADMIN_IDS", "123")
        with pytest.raises(ConfigError):
            Config.from_env()

    def test_from_env_invalid_admin_id(self, monkeypatch):
        monkeypatch.setenv("BOT_TOKEN", "test")
        monkeypatch.setenv("ADMIN_IDS", "abc")
        with pytest.raises(ConfigError):
            Config.from_env()

    def test_from_env_missing_admin_ids(self, monkeypatch):
        monkeypatch.setenv("BOT_TOKEN", "test")
        monkeypatch.setenv("ADMIN_IDS", "")
        with pytest.raises(ConfigError):
            Config.from_env()

    def test_from_env_invalid_promo_hour(self, monkeypatch):
        monkeypatch.setenv("BOT_TOKEN", "test")
        monkeypatch.setenv("ADMIN_IDS", "123")
        monkeypatch.setenv("PROMO_HOUR_UTC", "25")
        with pytest.raises(ConfigError):
            Config.from_env()

    def test_from_env_invalid_promo_minute(self, monkeypatch):
        monkeypatch.setenv("BOT_TOKEN", "test")
        monkeypatch.setenv("ADMIN_IDS", "123")
        monkeypatch.setenv("PROMO_MINUTE", "60")
        with pytest.raises(ConfigError):
            Config.from_env()

    def test_from_env_invalid_log_level(self, monkeypatch):
        monkeypatch.setenv("BOT_TOKEN", "test")
        monkeypatch.setenv("ADMIN_IDS", "123")
        monkeypatch.setenv("LOG_LEVEL", "VERBOSE")
        with pytest.raises(ConfigError):
            Config.from_env()

    def test_from_env_invalid_log_format(self, monkeypatch):
        monkeypatch.setenv("BOT_TOKEN", "test")
        monkeypatch.setenv("ADMIN_IDS", "123")
        monkeypatch.setenv("LOG_FORMAT", "xml")
        with pytest.raises(ConfigError):
            Config.from_env()

    def test_from_env_invalid_healthcheck_port(self, monkeypatch):
        monkeypatch.setenv("BOT_TOKEN", "test")
        monkeypatch.setenv("ADMIN_IDS", "123")
        monkeypatch.setenv("HEALTHCHECK_PORT", "99999")
        with pytest.raises(ConfigError):
            Config.from_env()
