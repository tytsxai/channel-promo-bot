import logging
from dataclasses import replace
from pathlib import Path

from src.config import config as base_config
from src.logging_setup import JsonFormatter, configure_logging


def test_configure_logging_text():
    cfg = replace(base_config, log_format="text", log_level="DEBUG", log_file=None)
    configure_logging(cfg)
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert root.handlers


def test_configure_logging_json():
    cfg = replace(base_config, log_format="json", log_level="INFO", log_file=None)
    configure_logging(cfg)
    root = logging.getLogger()
    assert any(isinstance(h.formatter, JsonFormatter) for h in root.handlers)


def test_configure_logging_adds_alert_handler(monkeypatch):
    fake_script = str(Path("/tmp/project/scripts/alert_admin.sh"))
    monkeypatch.setattr("src.logging_setup.os.path.isfile", lambda p: p == fake_script)
    monkeypatch.setattr("src.logging_setup.os.access", lambda p, mode: p == fake_script)

    original_resolve = Path.resolve

    def fake_resolve(self: Path):
        if str(self).endswith("src/logging_setup.py"):
            return Path("/tmp/project/src/logging_setup.py")
        return original_resolve(self)

    monkeypatch.setattr(Path, "resolve", fake_resolve)

    cfg = replace(
        base_config,
        log_format="text",
        log_level="INFO",
        log_file=None,
        alert_on_critical=True,
        alert_cooldown_seconds=60,
    )
    configure_logging(cfg)
    root = logging.getLogger()
    assert any(type(h).__name__ == "CriticalAlertHandler" for h in root.handlers)
