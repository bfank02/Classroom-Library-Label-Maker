"""Logging setup for production desktop use.

Handlers are attached only when :func:`setup_logging` is called so importing
this module (or any service module) never configures logging as a side effect.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

from classroom_library_label_maker.constants import (
    APP_LOGGER_NAME,
    DEFAULT_LOG_LEVEL,
    LOG_BACKUP_COUNT,
    LOG_MAX_BYTES,
)

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    level: str = DEFAULT_LOG_LEVEL,
    log_file: Path | None = None,
    *,
    logger_name: str = APP_LOGGER_NAME,
    max_bytes: int = LOG_MAX_BYTES,
    backup_count: int = LOG_BACKUP_COUNT,
) -> logging.Logger:
    """Configure and return the application logger.

    Attaches a stderr console handler and, when ``log_file`` is provided, a
    rotating file handler. Safe to call more than once; existing handlers on
    the named logger are cleared first.

    Args:
        level: Logging level name (e.g. ``\"INFO\"``, ``\"DEBUG\"``).
        log_file: Optional path for rotating file logs.
        logger_name: Root logger name for this application.
        max_bytes: Rotate when the log file exceeds this size.
        backup_count: Number of rotated backup files to retain.

    Returns:
        The configured :class:`logging.Logger` instance.
    """
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()
    logger.setLevel(_resolve_level(level))
    logger.propagate = False

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child logger under the application logger namespace.

    This function does not configure handlers. Call :func:`setup_logging`
    during application startup.

    Args:
        name: Optional dotted suffix (e.g. ``\"batch_processor\"``). When
            omitted, returns the root application logger.

    Returns:
        A :class:`logging.Logger` instance.
    """
    if name:
        return logging.getLogger(f"{APP_LOGGER_NAME}.{name}")
    return logging.getLogger(APP_LOGGER_NAME)


def _resolve_level(level: str) -> int:
    """Convert a level name to a logging level constant.

    Args:
        level: Level name such as ``\"INFO\"``.

    Returns:
        Corresponding ``logging`` module level integer.
    """
    resolved = logging.getLevelNamesMapping().get(level.upper())
    if resolved is None:
        return logging.INFO
    return resolved
