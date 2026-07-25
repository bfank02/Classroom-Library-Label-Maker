"""Application icon loading helpers for the desktop GUI."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon

from classroom_library_label_maker.config import ProjectPaths


def resolve_application_icon_path(
    *,
    project_root: Path | None = None,
) -> Path | None:
    """Return a usable application icon path, or ``None`` if none is ready.

    Looks for ``assets/icons/app.ico`` then ``assets/icons/logo.png``. Empty
    placeholder files (0 bytes) are treated as missing so packaging can add
    real artwork later without code changes.
    """
    paths = ProjectPaths(project_root)
    for candidate in (paths.app_icon_file, paths.logo_file):
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
