"""Tests for persistent GUI path preferences."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from classroom_library_label_maker.gui.app import create_application
from classroom_library_label_maker.gui.controller import GuiController
from classroom_library_label_maker.gui.main_window import MainWindow
from classroom_library_label_maker.gui_preferences import (
    GuiPreferences,
    load_gui_preferences,
    save_gui_preferences,
    usable_barcode_folder,
    usable_output_workbook,
)
from classroom_library_label_maker.user_paths import (
    barcode_folder_dialog_start_directory,
    label_workbook_save_dialog_defaults,
)


@pytest.fixture(scope="module")
def qapp():
    app = create_application(["classroom-library-label-maker-gui-prefs-test"])
    yield app


@pytest.fixture
def remembered_paths(tmp_path: Path) -> dict[str, Path]:
    barcodes = tmp_path / "barcodes"
    barcodes.mkdir()
    output_dir = tmp_path / "labels"
    output_dir.mkdir()
    output = output_dir / "library_labels.xlsx"
    return {"barcodes": barcodes, "output": output}


def test_save_and_load_gui_preferences_round_trip(tmp_path: Path) -> None:
    preferences_path = tmp_path / "prefs" / "gui_preferences.json"
    original = GuiPreferences(
        barcode_folder=tmp_path / "barcodes",
        output_workbook=tmp_path / "out" / "labels.xlsx",
    )
    save_gui_preferences(original, path=preferences_path)

    loaded = load_gui_preferences(path=preferences_path)
    assert loaded.barcode_folder == original.barcode_folder
    assert loaded.output_workbook == original.output_workbook
    payload = json.loads(preferences_path.read_text(encoding="utf-8"))
    assert payload["version"] == 1


def test_load_gui_preferences_missing_file_returns_empty(tmp_path: Path) -> None:
    loaded = load_gui_preferences(path=tmp_path / "missing.json")
    assert loaded == GuiPreferences()


def test_load_gui_preferences_corrupt_file_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "gui_preferences.json"
    path.write_text("{not-json", encoding="utf-8")
    assert load_gui_preferences(path=path) == GuiPreferences()


def test_usable_paths_reject_missing_locations(tmp_path: Path) -> None:
    missing_dir = tmp_path / "gone"
    missing_parent = tmp_path / "missing-parent" / "labels.xlsx"
    assert usable_barcode_folder(missing_dir) is None
    assert usable_output_workbook(missing_parent) is None
    assert usable_output_workbook(tmp_path / "notes.txt") is None


def test_dialog_helpers_prefer_remembered_paths(
    remembered_paths: dict[str, Path],
) -> None:
    barcodes = remembered_paths["barcodes"]
    output = remembered_paths["output"]
    assert barcode_folder_dialog_start_directory(
        last_barcode_folder=barcodes
    ) == str(barcodes.resolve())
    start_dir, name = label_workbook_save_dialog_defaults(
        last_output_workbook=output
    )
    assert start_dir == str(output.parent.resolve())
    assert name == output.name


def test_controller_restores_remembered_paths(
    qapp, remembered_paths: dict[str, Path], tmp_path: Path
) -> None:
    preferences_path = tmp_path / "remembered.json"
    save_gui_preferences(
        GuiPreferences(
            barcode_folder=remembered_paths["barcodes"],
            output_workbook=remembered_paths["output"],
        ),
        path=preferences_path,
    )

    window = MainWindow()
    controller = GuiController(window, preferences_path=preferences_path)

    assert controller.state.barcode_folder == remembered_paths["barcodes"].resolve()
    assert controller.state.output_workbook == remembered_paths["output"].resolve()
    assert remembered_paths["barcodes"].name in window.barcode_path_label.text()
    assert remembered_paths["output"].name in window.output_path_label.text()
    window.close()


def test_controller_skips_stale_remembered_paths(
    qapp, tmp_path: Path
) -> None:
    preferences_path = tmp_path / "stale.json"
    save_gui_preferences(
        GuiPreferences(
            barcode_folder=tmp_path / "deleted-barcodes",
            output_workbook=tmp_path / "deleted-dir" / "labels.xlsx",
        ),
        path=preferences_path,
    )

    window = MainWindow()
    controller = GuiController(window, preferences_path=preferences_path)

    assert controller.state.barcode_folder is None
    assert controller.state.output_workbook is None
    window.close()


def test_controller_persists_paths_on_set(
    qapp, remembered_paths: dict[str, Path], tmp_path: Path
) -> None:
    preferences_path = tmp_path / "write.json"
    window = MainWindow()
    controller = GuiController(window, preferences_path=preferences_path)

    controller.set_barcode_folder(remembered_paths["barcodes"])
    controller.set_output_workbook(remembered_paths["output"])

    loaded = load_gui_preferences(path=preferences_path)
    assert loaded.barcode_folder == remembered_paths["barcodes"].resolve()
    assert loaded.output_workbook == remembered_paths["output"].resolve()
    window.close()
