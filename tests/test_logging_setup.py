import logging
from dataclasses import replace

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
