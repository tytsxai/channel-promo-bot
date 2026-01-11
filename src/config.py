from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    """Raised when configuration is invalid."""


def _get_str(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _get_int(
    name: str,
    default: int,
    *,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        value = default
    else:
        try:
            value = int(raw)
        except ValueError as exc:
            raise ConfigError(f"{name} must be an integer, got '{raw}'") from exc
    if min_value is not None and value < min_value:
        raise ConfigError(f"{name} must be >= {min_value}, got {value}")
    if max_value is not None and value > max_value:
        raise ConfigError(f"{name} must be <= {max_value}, got {value}")
    return value


def _get_float(
    name: str,
    default: float,
    *,
    min_value: float | None = None,
    max_value: float | None = None,
) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        value = default
    else:
        try:
            value = float(raw)
        except ValueError as exc:
            raise ConfigError(f"{name} must be a float, got '{raw}'") from exc
    if min_value is not None and value < min_value:
        raise ConfigError(f"{name} must be >= {min_value}, got {value}")
    if max_value is not None and value > max_value:
        raise ConfigError(f"{name} must be <= {max_value}, got {value}")
    return value


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    raise ConfigError(f"{name} must be a boolean, got '{raw}'")


def _get_optional_str(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _get_admin_ids(raw: str) -> list[int]:
    admin_ids: list[int] = []
    for value in raw.split(","):
        value = value.strip()
        if not value:
            continue
        try:
            admin_ids.append(int(value))
        except ValueError as exc:
            raise ConfigError(f"Invalid ADMIN_ID: {value}") from exc
    return sorted(set(admin_ids))


def _get_log_format(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"text", "json"}:
        raise ConfigError("LOG_FORMAT must be 'text' or 'json'")
    return normalized


def _get_log_level(value: str) -> str:
    normalized = value.strip().upper()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if normalized not in valid_levels:
        raise ConfigError(f"LOG_LEVEL must be one of {sorted(valid_levels)}")
    return normalized


def _get_rate_limit_storage(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"memory", "sqlite"}:
        raise ConfigError("RATE_LIMIT_STORAGE must be 'memory' or 'sqlite'")
    return normalized


def _validate_production_config(cfg: "Config") -> None:
    if cfg.environment.lower() != "production":
        return
    if not cfg.instance_lock_enabled:
        raise ConfigError("INSTANCE_LOCK_ENABLED must be true in production")
    if cfg.healthcheck_port == 0:
        raise ConfigError("HEALTHCHECK_PORT must be set in production")
    if cfg.database_path == ":memory:":
        raise ConfigError("DATABASE_PATH must not be ':memory:' in production")


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: list[int]
    bot_description: str | None
    bot_short_description: str | None
    openai_api_key: str
    openai_model: str
    openai_base_url: str | None
    min_members: int
    database_path: str
    promo_hour_utc: int
    promo_minute: int
    promo_concurrency: int
    promo_send_interval: float
    promo_lock_enabled: bool
    promo_lock_ttl: int
    promo_batch_size: int
    promo_shutdown_timeout: int
    rate_limit: int
    rate_limit_window: int
    rate_limit_cleanup: int
    rate_limit_storage: str
    log_level: str
    log_format: str
    log_file: str | None
    log_max_bytes: int
    log_backup_count: int
    healthcheck_host: str
    healthcheck_port: int
    instance_lock_enabled: bool
    instance_lock_path: str
    environment: str

    @classmethod
    def from_env(cls) -> Config:
        bot_token = _get_str("BOT_TOKEN")
        if not bot_token:
            raise ConfigError("BOT_TOKEN is required")

        admin_ids_raw = _get_str("ADMIN_IDS")
        admin_ids = _get_admin_ids(admin_ids_raw)
        if not admin_ids:
            raise ConfigError("At least one ADMIN_ID is required")

        promo_hour = _get_int("PROMO_HOUR_UTC", 5, min_value=0, max_value=23)
        promo_minute = _get_int("PROMO_MINUTE", 0, min_value=0, max_value=59)
        database_path = _get_str("DATABASE_PATH", "data/bot.db")
        default_lock_path = os.path.join(os.path.dirname(database_path), "bot.lock")
        if not os.path.dirname(default_lock_path):
            default_lock_path = "bot.lock"

        cfg = cls(
            bot_token=bot_token,
            admin_ids=admin_ids,
            bot_description=_get_optional_str("BOT_DESCRIPTION"),
            bot_short_description=_get_optional_str("BOT_SHORT_DESCRIPTION"),
            openai_api_key=_get_str("OPENAI_API_KEY"),
            openai_model=_get_str("OPENAI_MODEL", "gpt-3.5-turbo"),
            openai_base_url=_get_optional_str("OPENAI_BASE_URL"),
            min_members=_get_int("MIN_MEMBERS", 700, min_value=1),
            database_path=database_path,
            promo_hour_utc=promo_hour,
            promo_minute=promo_minute,
            promo_concurrency=_get_int("PROMO_CONCURRENCY", 5, min_value=1),
            promo_send_interval=_get_float("PROMO_SEND_INTERVAL", 0.05, min_value=0.0),
            promo_lock_enabled=_get_bool("PROMO_LOCK_ENABLED", True),
            promo_lock_ttl=_get_int("PROMO_LOCK_TTL", 3600, min_value=60),
            promo_batch_size=_get_int("PROMO_BATCH_SIZE", 500, min_value=1),
            promo_shutdown_timeout=_get_int(
                "PROMO_SHUTDOWN_TIMEOUT", 30, min_value=0
            ),
            rate_limit=_get_int("RATE_LIMIT", 10, min_value=1),
            rate_limit_window=_get_int("RATE_LIMIT_WINDOW", 60, min_value=1),
            rate_limit_cleanup=_get_int("RATE_LIMIT_CLEANUP", 300, min_value=1),
            rate_limit_storage=_get_rate_limit_storage(
                _get_str("RATE_LIMIT_STORAGE", "sqlite")
            ),
            log_level=_get_log_level(_get_str("LOG_LEVEL", "INFO")),
            log_format=_get_log_format(_get_str("LOG_FORMAT", "text")),
            log_file=_get_optional_str("LOG_FILE"),
            log_max_bytes=_get_int("LOG_MAX_BYTES", 10_485_760, min_value=1),
            log_backup_count=_get_int("LOG_BACKUP_COUNT", 5, min_value=0),
            healthcheck_host=_get_str("HEALTHCHECK_HOST", "127.0.0.1"),
            healthcheck_port=_get_int("HEALTHCHECK_PORT", 0, min_value=0, max_value=65535),
            instance_lock_enabled=_get_bool("INSTANCE_LOCK_ENABLED", True),
            instance_lock_path=_get_str("INSTANCE_LOCK_PATH", default_lock_path),
            environment=_get_str("ENVIRONMENT", "production"),
        )
        _validate_production_config(cfg)
        return cfg


config = Config.from_env()
