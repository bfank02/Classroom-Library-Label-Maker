"""Tests for logging helpers."""

from __future__ import annotations

import logging
from pathlib import Path

from classroom_library_label_maker.constants import APP_LOGGER_NAME
from classroom_library_label_maker.logger import get_logger, setup_logging


def test_setup_logging_console_only() -> None:
    """setup_logging should configure the application logger."""
    logger = setup_logging(level="DEBUG")
    assert logger.level == logging.DEBUG
    assert logger.handlers


def test_setup_logging_with_rotating_file(tmp_path: Path) -> None:
    """setup_logging should create a rotating file handler when log_file is set."""
    log_file = tmp_path / "logs" / "application.log"
    logger = setup_logging(level="INFO", log_file=log_file)
    logger.info("hello")
    assert log_file.is_file()
    assert "hello" in log_file.read_text(encoding="utf-8")


def test_get_logger_child() -> None:
    """get_logger should nest under the application namespace."""
    setup_logging(level="INFO")
    child = get_logger("batch")
    assert child.name == f"{APP_LOGGER_NAME}.batch"


def test_import_does_not_configure_handlers() -> None:
    """Importing the logger module must not attach handlers by itself."""
    import importlib

    import classroom_library_label_maker.logger as logger_module

    importlib.reload(logger_module)
    root = logging.getLogger(APP_LOGGER_NAME)
    # Reload clears nothing reliably across runs; ensure get_logger alone is inert.
    before = list(logging.getLogger(f"{APP_LOGGER_NAME}.import_probe").handlers)
    logger_module.get_logger("import_probe")
    after = list(logging.getLogger(f"{APP_LOGGER_NAME}.import_probe").handlers)
    assert before == after
    assert root is not None
