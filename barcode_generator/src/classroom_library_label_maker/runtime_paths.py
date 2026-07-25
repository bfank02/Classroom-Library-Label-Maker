"""Platform-localized path helpers for packaged and development runs.

Application logic should call these helpers (or :class:`ProjectPaths`) instead
of scattering ``sys.platform`` / frozen checks through the codebase.

Platform-specific directories exist because each OS defines different
conventions for user-writable logs and application support data; a single
hardcoded path cannot be correct on both Windows and macOS.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from classroom_library_label_maker.metadata import APP_NAME


def is_frozen_application() -> bool:
    """Return True when running inside a PyInstaller (or similar) bundle."""
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def bundled_resource_root() -> Path:
    """Return the read-only root that contains bundled ``assets/``.

    In a frozen build this is PyInstaller's extract/bundle directory
    (``sys._MEIPASS``). In development it is discovered by the caller via
    :func:`~classroom_library_label_maker.config.find_project_root`.
    """
    if is_frozen_application():
        return Path(sys._MEIPASS).resolve()  # type: ignore[attr-defined]
    raise RuntimeError(
        "bundled_resource_root() is only valid in a frozen application; "
        "use find_project_root() during development."
    )


def user_data_directory(*, app_name: str = APP_NAME) -> Path:
    """Return a per-user writable application data directory.

    * macOS: ``~/Library/Application Support/<app_name>/``
    * Windows: ``%LOCALAPPDATA%/<app_name>/``
    * Other: ``~/.local/share/<app_name>/``
    """
    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support" / app_name).resolve()
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return (base / app_name).resolve()
    return (Path.home() / ".local" / "share" / app_name).resolve()


def user_log_directory(*, app_name: str = APP_NAME) -> Path:
    """Return a per-user writable log directory.

    * macOS: ``~/Library/Logs/<app_name>/`` (system log convention)
    * Windows: ``%LOCALAPPDATA%/<app_name>/logs/``
    * Other: ``~/.local/state/<app_name>/logs/``

    macOS uses ``Library/Logs`` rather than nesting under Application Support
    because that is the platform convention teachers and support tools expect.
    """
    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Logs" / app_name).resolve()
    if sys.platform == "win32":
        return (user_data_directory(app_name=app_name) / "logs").resolve()
    return (Path.home() / ".local" / "state" / app_name / "logs").resolve()
