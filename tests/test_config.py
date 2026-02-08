import os

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
        assert config.rate_limit_storage in {"memory", "sqlite"}

    def test_promo_tuning_defaults(self):
        from src.config import config
        assert config.promo_concurrency >= 1
        assert config.promo_send_interval >= 0.0
        assert config.promo_lock_ttl >= 60
        assert config.promo_batch_size >= 1
        assert config.promo_shutdown_timeout >= 0

    def test_logging_defaults(self):
        from src.config import config
        assert config.log_level == "INFO"
        assert config.log_format == "text"
        expected = os.environ.get("LOG_FILE")
        assert config.log_file == expected

    def test_healthcheck_defaults(self):
        from src.config import config
        assert config.healthcheck_port == 0
        assert config.healthcheck_host == "127.0.0.1"
        assert config.instance_lock_enabled is True
        assert config.instance_lock_path
        assert config.alert_on_critical is True
        assert config.alert_cooldown_seconds >= 0

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

    def test_from_env_invalid_rate_limit_storage(self, monkeypatch):
        monkeypatch.setenv("BOT_TOKEN", "test")
        monkeypatch.setenv("ADMIN_IDS", "123")
        monkeypatch.setenv("RATE_LIMIT_STORAGE", "redis")
        with pytest.raises(ConfigError):
            Config.from_env()

    def test_from_env_invalid_promo_batch(self, monkeypatch):
        monkeypatch.setenv("BOT_TOKEN", "test")
        monkeypatch.setenv("ADMIN_IDS", "123")
        monkeypatch.setenv("PROMO_BATCH_SIZE", "0")
        with pytest.raises(ConfigError):
            Config.from_env()

    def test_from_env_invalid_healthcheck_port(self, monkeypatch):
        monkeypatch.setenv("BOT_TOKEN", "test")
        monkeypatch.setenv("ADMIN_IDS", "123")
        monkeypatch.setenv("HEALTHCHECK_PORT", "99999")
        with pytest.raises(ConfigError):
            Config.from_env()

    def test_from_env_invalid_promo_shutdown_timeout(self, monkeypatch):
        monkeypatch.setenv("BOT_TOKEN", "test")
        monkeypatch.setenv("ADMIN_IDS", "123")
        monkeypatch.setenv("PROMO_SHUTDOWN_TIMEOUT", "-1")
        with pytest.raises(ConfigError):
            Config.from_env()

    def test_from_env_instance_lock_disabled(self, monkeypatch):
        monkeypatch.setenv("BOT_TOKEN", "test")
        monkeypatch.setenv("ADMIN_IDS", "123")
        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.setenv("INSTANCE_LOCK_ENABLED", "false")
        cfg = Config.from_env()
        assert cfg.instance_lock_enabled is False

    def test_from_env_production_requires_healthcheck(self, monkeypatch):
        monkeypatch.setenv("BOT_TOKEN", "test")
        monkeypatch.setenv("ADMIN_IDS", "123")
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("HEALTHCHECK_PORT", "0")
        with pytest.raises(ConfigError):
            Config.from_env()

    def test_from_env_production_requires_instance_lock(self, monkeypatch):
        monkeypatch.setenv("BOT_TOKEN", "test")
        monkeypatch.setenv("ADMIN_IDS", "123")
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("HEALTHCHECK_PORT", "8080")
        monkeypatch.setenv("INSTANCE_LOCK_ENABLED", "false")
        with pytest.raises(ConfigError):
            Config.from_env()

    def test_from_env_production_disallows_memory_db(self, monkeypatch):
        monkeypatch.setenv("BOT_TOKEN", "test")
        monkeypatch.setenv("ADMIN_IDS", "123")
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("HEALTHCHECK_PORT", "8080")
        monkeypatch.setenv("DATABASE_PATH", ":memory:")
        with pytest.raises(ConfigError):
            Config.from_env()

    def test_from_env_invalid_alert_cooldown(self, monkeypatch):
        monkeypatch.setenv("BOT_TOKEN", "test")
        monkeypatch.setenv("ADMIN_IDS", "123")
        monkeypatch.setenv("ALERT_COOLDOWN_SECONDS", "-1")
        with pytest.raises(ConfigError):
            Config.from_env()
