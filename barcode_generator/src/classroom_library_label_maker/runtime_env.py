"""Runtime environment helpers for source installs and frozen releases.

Keeps packaging concerns out of business services. Safe to import early.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from classroom_library_label_maker.constants import (
    DEFAULT_LOG_FILE_NAME,
    DIR_LOGS,
)
from classroom_library_label_maker.metadata import APP_NAME


def is_frozen() -> bool:
    """Return True when running from a PyInstaller (or similar) bundle."""
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def bundle_directory() -> Path | None:
    """Return the PyInstaller extraction directory, or ``None`` when not frozen."""
    if not is_frozen():
        return None
    return Path(sys._MEIPASS)  # type: ignore[attr-defined]


def resource_root() -> Path:
    """Return the directory that contains bundled ``assets/``.

    Frozen builds use ``sys._MEIPASS``. Source/editable installs use the
    ``barcode_generator`` project root.
    """
    bundled = bundle_directory()
    if bundled is not None:
        return bundled.resolve()

    from classroom_library_label_maker.config import find_project_root

    return find_project_root().resolve()


def user_app_data_directory() -> Path:
    """Return a per-user, writable application data directory.

    Windows: ``%LOCALAPPDATA%\\Classroom Library Label Maker``
    macOS: ``~/Library/Application Support/Classroom Library Label Maker``
    other: ``~/.local/share/Classroom Library Label Maker``
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return (base / APP_NAME).resolve()


def default_user_log_directory() -> Path:
    """Return the default rotating-log directory under user app data."""
    return user_app_data_directory() / DIR_LOGS


def default_user_log_file() -> Path:
    """Return the default application log file path for desktop use."""
    return default_user_log_directory() / DEFAULT_LOG_FILE_NAME
