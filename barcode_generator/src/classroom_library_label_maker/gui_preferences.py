"""Persistent GUI path preferences for the desktop app.

Stores last-used inventory workbook, barcode folder, label folder, and label
filename under the platform user-data directory so teachers do not re-select
them every launch. Also remembers the review-wizard inventory-save preference.

Qt-free: safe to import from tests and path helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from classroom_library_label_maker.constants import (
    DEFAULT_LABEL_FILENAME,
    GUI_PREFERENCES_FILE_NAME,
)
from classroom_library_label_maker.runtime_paths import user_data_directory

_PREFERENCES_VERSION = 2


@dataclass(frozen=True, slots=True)
class GuiPreferences:
    """Remembered GUI path selections and review preferences."""

    inventory_workbook: Path | None = None
    barcode_folder: Path | None = None
    label_folder: Path | None = None
    label_filename: str | None = None
    save_updated_inventory_on_review: bool = True

    @property
    def output_workbook(self) -> Path | None:
        """Legacy convenience: folder + filename when both are present."""
        if self.label_folder is None:
            return None
        name = (self.label_filename or "").strip()
        if not name:
            return None
        return self.label_folder / name


def default_gui_preferences_path() -> Path:
    """Return the default on-disk preferences file path."""
    return user_data_directory() / GUI_PREFERENCES_FILE_NAME


def usable_inventory_workbook(path: Path | None) -> Path | None:
    """Return ``path`` when it exists as a file; otherwise ``None``."""
    if path is None:
        return None
    try:
        if path.is_file():
            return path.resolve()
    except OSError:
        return None
    return None


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


def usable_label_folder(path: Path | None) -> Path | None:
    """Return ``path`` when it exists as a directory; otherwise ``None``."""
    return usable_barcode_folder(path)


def usable_label_filename(filename: str | None) -> str | None:
    """Return a cleaned Excel filename, or ``None`` when empty/invalid suffix."""
    if filename is None:
        return None
    cleaned = filename.strip()
    if not cleaned:
        return None
    suffix = Path(cleaned).suffix.lower()
    if suffix not in {".xlsx", ".xlsm"}:
        return None
    # Reject path separators smuggled into the name field.
    if "/" in cleaned or "\\" in cleaned:
        return None
    return cleaned


def usable_output_workbook(path: Path | None) -> Path | None:
    """Return ``path`` when its parent exists and the suffix is Excel.

    The workbook file itself need not exist yet (save-as target). Kept for
    migration of legacy preferences that stored a full output path.
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
    """Load preferences from disk, ignoring missing or corrupt files.

    Supports legacy ``output_workbook`` by splitting into folder + filename.
    """
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
    save_flag = payload.get("save_updated_inventory_on_review", True)
    if not isinstance(save_flag, bool):
        save_flag = True

    label_folder = _optional_path(payload.get("label_folder"))
    label_filename = _optional_filename(payload.get("label_filename"))
    legacy_output = _optional_path(payload.get("output_workbook"))
    if label_folder is None and legacy_output is not None:
        label_folder = legacy_output.parent
        if label_filename is None:
            label_filename = legacy_output.name

    return GuiPreferences(
        inventory_workbook=_optional_path(payload.get("inventory_workbook")),
        barcode_folder=_optional_path(payload.get("barcode_folder")),
        label_folder=label_folder,
        label_filename=label_filename,
        save_updated_inventory_on_review=save_flag,
    )


def save_gui_preferences(
    preferences: GuiPreferences,
    *,
    path: Path | None = None,
) -> None:
    """Write preferences to disk, creating the parent directory when needed."""
    preferences_path = path if path is not None else default_gui_preferences_path()
    filename = preferences.label_filename
    if filename is None or not str(filename).strip():
        filename = DEFAULT_LABEL_FILENAME
    payload: dict[str, Any] = {
        "version": _PREFERENCES_VERSION,
        "inventory_workbook": _path_to_str(preferences.inventory_workbook),
        "barcode_folder": _path_to_str(preferences.barcode_folder),
        "label_folder": _path_to_str(preferences.label_folder),
        "label_filename": str(filename).strip(),
        "save_updated_inventory_on_review": (
            preferences.save_updated_inventory_on_review
        ),
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


def _optional_filename(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _path_to_str(path: Path | None) -> str | None:
    return str(path) if path is not None else None
