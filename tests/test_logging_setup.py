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


def test_json_formatter_basic():
    import json
    import logging

    from src.logging_setup import JsonFormatter

    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="hello world",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "hello world"
    assert "timestamp" in parsed
    assert "logger" in parsed


def test_json_formatter_with_exception():
    import json
    import logging
    import sys

    from src.logging_setup import JsonFormatter

    formatter = JsonFormatter()
    try:
        raise ValueError("test error")
    except ValueError:
        exc_info = sys.exc_info()
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname="",
        lineno=0,
        msg="oops",
        args=(),
        exc_info=exc_info,
    )
    output = formatter.format(record)
    parsed = json.loads(output)
    assert "exc_info" in parsed
    assert "ValueError" in parsed["exc_info"]


def test_critical_alert_handler_cooldown():
    import logging
    import time

    from src.logging_setup import CriticalAlertHandler

    handler = CriticalAlertHandler(script_path="/nonexistent/script.sh", cooldown_seconds=9999)
    handler._last_sent = time.time()  # 模拟刚发送过
    record = logging.LogRecord(
        name="test", level=logging.ERROR, pathname="", lineno=0, msg="alert", args=(), exc_info=None
    )
    # 冷却中，不应触发 Popen
    import unittest.mock as mock

    with mock.patch("subprocess.Popen") as popen_mock:
        handler.emit(record)
        popen_mock.assert_not_called()


def test_critical_alert_handler_fires_after_cooldown():
    import logging
    import unittest.mock as mock

    from src.logging_setup import CriticalAlertHandler

    handler = CriticalAlertHandler(script_path="/nonexistent/script.sh", cooldown_seconds=0)
    handler._last_sent = 0.0
    record = logging.LogRecord(
        name="test", level=logging.ERROR, pathname="", lineno=0, msg="alert", args=(), exc_info=None
    )
    with mock.patch("subprocess.Popen") as popen_mock:
        popen_mock.return_value = None
        handler.emit(record)
        popen_mock.assert_called_once()


def test_critical_alert_handler_below_level_skipped():
    import logging
    import unittest.mock as mock

    from src.logging_setup import CriticalAlertHandler

    handler = CriticalAlertHandler(script_path="/nonexistent/script.sh", cooldown_seconds=0)
    handler._last_sent = 0.0
    record = logging.LogRecord(
        name="test",
        level=logging.DEBUG,
        pathname="",
        lineno=0,
        msg="debug msg",
        args=(),
        exc_info=None,
    )
    with mock.patch("subprocess.Popen") as popen_mock:
        handler.emit(record)
        popen_mock.assert_not_called()


def test_configure_logging_with_file(tmp_path):
    from dataclasses import replace

    from src.config import config as base_config
    from src.logging_setup import configure_logging

    log_file = str(tmp_path / "test.log")
    cfg = replace(
        base_config,
        log_format="text",
        log_level="WARNING",
        log_file=log_file,
    )
    configure_logging(cfg)
    root = logging.getLogger()
    from logging.handlers import RotatingFileHandler

    assert any(isinstance(h, RotatingFileHandler) for h in root.handlers)


def test_configure_logging_alert_script_not_executable(monkeypatch):
    """alert_on_critical=True 但脚本不可执行时不应添加 CriticalAlertHandler。"""
    from dataclasses import replace

    from src.config import config as base_config
    from src.logging_setup import configure_logging

    monkeypatch.setattr("src.logging_setup.os.path.isfile", lambda p: True)
    monkeypatch.setattr("src.logging_setup.os.access", lambda p, mode: False)
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
    assert not any(type(h).__name__ == "CriticalAlertHandler" for h in root.handlers)
