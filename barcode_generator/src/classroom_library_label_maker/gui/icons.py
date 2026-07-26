"""Application icon loading helpers for the desktop GUI."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon

from classroom_library_label_maker.config import ProjectPaths


def resolve_application_icon_path(
    *,
    project_root: Path | None = None,
) -> Path | None:
    """Return a usable application icon path, or ``None`` if none is ready.

    Prefers the platform-native icon format when present, then falls back to
    ``logo.png`` and finally the alternate packaged icon. Empty placeholder
    files (0 bytes) are treated as missing.
    """
    paths = ProjectPaths(project_root)
    if sys.platform == "darwin":
        candidates = (paths.app_icns_file, paths.logo_file, paths.app_icon_file)
    elif sys.platform == "win32":
        candidates = (paths.app_icon_file, paths.logo_file, paths.app_icns_file)
    else:
        candidates = (paths.logo_file, paths.app_icon_file, paths.app_icns_file)

    for candidate in candidates:
        try:
            if candidate.is_file() and candidate.stat().st_size > 0:
                return candidate
        except OSError:
            continue
    return None


def load_application_icon(*, project_root: Path | None = None) -> QIcon:
    """Load the application icon, or an empty ``QIcon`` when unavailable."""
    path = resolve_application_icon_path(project_root=project_root)
    if path is None:
        return QIcon()
    return QIcon(str(path))
