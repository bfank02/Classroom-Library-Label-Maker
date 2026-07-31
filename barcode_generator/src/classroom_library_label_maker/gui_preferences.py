"""Persistent GUI path preferences for the desktop app.

Stores last-used barcode folder and label workbook paths under the
platform user-data directory so teachers do not re-select them every launch.
Qt-free: safe to import from tests and path helpers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from classroom_library_label_maker.constants import GUI_PREFERENCES_FILE_NAME
from classroom_library_label_maker.runtime_paths import user_data_directory

_PREFERENCES_VERSION = 1


@dataclass(frozen=True, slots=True)
class GuiPreferences:
    """Remembered GUI path selections."""

    barcode_folder: Path | None = None
    output_workbook: Path | None = None


def default_gui_preferences_path() -> Path:
    """Return the default on-disk preferences file path."""
    return user_data_directory() / GUI_PREFERENCES_FILE_NAME


def usable_barcode_folder(path: Path | None) -> Path | None:
    """Return ``path`` when it exists as a directory; otherwise ``None``."""
    if path is None:
        return None
    try:
        if path.is_dir():
            return path.resolve()
    except OSError:
        return None
    return None


def usable_output_workbook(path: Path | None) -> Path | None:
    """Return ``path`` when its parent exists and the suffix is Excel.

    The workbook file itself need not exist yet (save-as target).
    """
    if path is None:
        return None
    try:
        resolved = path.resolve()
    except OSError:
        return None
    if resolved.suffix.lower() not in {".xlsx", ".xlsm"}:
        return None
    parent = resolved.parent
    if str(parent) in ("", "."):
        return None
    try:
        if not parent.is_dir():
            return None
    except OSError:
        return None
    return resolved


def load_gui_preferences(*, path: Path | None = None) -> GuiPreferences:
    """Load preferences from disk, ignoring missing or corrupt files."""
    preferences_path = path if path is not None else default_gui_preferences_path()
    try:
        raw = preferences_path.read_text(encoding="utf-8")
    except OSError:
        return GuiPreferences()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return GuiPreferences()
    if not isinstance(payload, dict):
        return GuiPreferences()
    return GuiPreferences(
        barcode_folder=_optional_path(payload.get("barcode_folder")),
        output_workbook=_optional_path(payload.get("output_workbook")),
    )


def save_gui_preferences(
    preferences: GuiPreferences,
    *,
    path: Path | None = None,
) -> None:
    """Write preferences to disk, creating the parent directory when needed."""
    preferences_path = path if path is not None else default_gui_preferences_path()
    payload: dict[str, Any] = {
        "version": _PREFERENCES_VERSION,
        "barcode_folder": _path_to_str(preferences.barcode_folder),
        "output_workbook": _path_to_str(preferences.output_workbook),
    }
    preferences_path.parent.mkdir(parents=True, exist_ok=True)
    preferences_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _optional_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return Path(value)


def _path_to_str(path: Path | None) -> str | None:
    return str(path) if path is not None else None
