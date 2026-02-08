import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

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


class CriticalAlertHandler(logging.Handler):
    def __init__(self, script_path: str, cooldown_seconds: int):
        super().__init__(level=logging.ERROR)
        self._script_path = script_path
        self._cooldown_seconds = max(0, cooldown_seconds)
        self._last_sent = 0.0
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno < self.level:
            return
        now = time.time()
        with self._lock:
            if (
                self._cooldown_seconds > 0
                and now - self._last_sent < self._cooldown_seconds
            ):
                return
            self._last_sent = now
        try:
            message = self.format(record)
            subprocess.Popen(
                [self._script_path, message],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        except Exception:
            # Must never break main logging flow.
            return


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

    if config.alert_on_critical:
        project_root = Path(__file__).resolve().parent.parent
        script_path = str(project_root / "scripts" / "alert_admin.sh")
        if os.path.isfile(script_path) and os.access(script_path, os.X_OK):
            alert_handler = CriticalAlertHandler(
                script_path, config.alert_cooldown_seconds
            )
            alert_handler.setFormatter(
                logging.Formatter(
                    "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s"
                )
            )
            handlers.append(alert_handler)

    if config.log_format == "json":
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    for handler in handlers:
        if not isinstance(handler, CriticalAlertHandler):
            handler.setFormatter(formatter)

    logging.basicConfig(level=config.log_level, handlers=handlers, force=True)
    logging.captureWarnings(True)
