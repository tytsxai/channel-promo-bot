import json
import logging
import os
import sys
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler

from src.config import Config


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(config: Config) -> None:
    handlers: list[logging.Handler] = []

    stream_handler = logging.StreamHandler(sys.stdout)
    handlers.append(stream_handler)

    if config.log_file:
        log_dir = os.path.dirname(config.log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
            config.log_file,
            maxBytes=config.log_max_bytes,
            backupCount=config.log_backup_count,
            encoding="utf-8",
        )
        handlers.append(file_handler)

    if config.log_format == "json":
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    for handler in handlers:
        handler.setFormatter(formatter)

    logging.basicConfig(level=config.log_level, handlers=handlers, force=True)
    logging.captureWarnings(True)
