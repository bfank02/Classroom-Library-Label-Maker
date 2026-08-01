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
    label_folder_dialog_start_directory,
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
    inventory = tmp_path / "inventory.xlsx"
    inventory.write_bytes(b"PK\x03\x04")
    return {
        "inventory": inventory,
        "barcodes": barcodes,
        "label_folder": output_dir,
        "output": output,
    }


def test_save_and_load_gui_preferences_round_trip(tmp_path: Path) -> None:
    preferences_path = tmp_path / "prefs" / "gui_preferences.json"
    original = GuiPreferences(
        inventory_workbook=tmp_path / "books.xlsx",
        barcode_folder=tmp_path / "barcodes",
        label_folder=tmp_path / "out",
        label_filename="labels.xlsx",
    )
    save_gui_preferences(original, path=preferences_path)

    loaded = load_gui_preferences(path=preferences_path)
    assert loaded.barcode_folder == original.barcode_folder
    assert loaded.label_folder == original.label_folder
    assert loaded.label_filename == "labels.xlsx"
    assert loaded.inventory_workbook == original.inventory_workbook
    payload = json.loads(preferences_path.read_text(encoding="utf-8"))
    assert payload["version"] == 2
    assert "output_workbook" not in payload


def test_load_gui_preferences_migrates_legacy_output_workbook(tmp_path: Path) -> None:
    preferences_path = tmp_path / "legacy.json"
    preferences_path.write_text(
        json.dumps(
            {
                "version": 1,
                "barcode_folder": str(tmp_path / "barcodes"),
                "output_workbook": str(tmp_path / "out" / "old_labels.xlsx"),
                "save_updated_inventory_on_review": True,
            }
        ),
        encoding="utf-8",
    )
    loaded = load_gui_preferences(path=preferences_path)
    assert loaded.label_folder == tmp_path / "out"
    assert loaded.label_filename == "old_labels.xlsx"


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
    assert label_folder_dialog_start_directory(
        last_label_folder=remembered_paths["label_folder"]
    ) == str(remembered_paths["label_folder"].resolve())
    start_dir, name = label_workbook_save_dialog_defaults(
        last_label_folder=remembered_paths["label_folder"],
        last_label_filename=output.name,
    )
    assert start_dir == str(remembered_paths["label_folder"].resolve())
    assert name == output.name


def test_controller_restores_remembered_paths(
    qapp, remembered_paths: dict[str, Path], tmp_path: Path
) -> None:
    preferences_path = tmp_path / "remembered.json"
    save_gui_preferences(
        GuiPreferences(
            inventory_workbook=remembered_paths["inventory"],
            barcode_folder=remembered_paths["barcodes"],
            label_folder=remembered_paths["label_folder"],
            label_filename=remembered_paths["output"].name,
        ),
        path=preferences_path,
    )

    window = MainWindow()
    controller = GuiController(window, preferences_path=preferences_path)

    assert controller.state.inventory_workbook == remembered_paths["inventory"].resolve()
    assert controller.state.barcode_folder == remembered_paths["barcodes"].resolve()
    assert controller.state.label_folder == remembered_paths["label_folder"].resolve()
    assert controller.state.label_filename == remembered_paths["output"].name
    assert remembered_paths["barcodes"].name in window.barcode_path_label.text()
    assert remembered_paths["label_folder"].name in window.output_path_label.text()
    assert window.filename_edit.text() == remembered_paths["output"].name
    window.close()


def test_controller_skips_stale_remembered_paths(
    qapp, tmp_path: Path
) -> None:
    preferences_path = tmp_path / "stale.json"
    save_gui_preferences(
        GuiPreferences(
            barcode_folder=tmp_path / "deleted-barcodes",
            label_folder=tmp_path / "deleted-dir",
            label_filename="labels.xlsx",
        ),
        path=preferences_path,
    )

    window = MainWindow()
    controller = GuiController(window, preferences_path=preferences_path)

    assert controller.state.barcode_folder is None
    assert controller.state.label_folder is None
    assert controller.state.label_filename == "labels.xlsx"
    window.close()


def test_controller_persists_paths_on_set(
    qapp, remembered_paths: dict[str, Path], tmp_path: Path
) -> None:
    preferences_path = tmp_path / "write.json"
    window = MainWindow()
    controller = GuiController(window, preferences_path=preferences_path)

    controller.set_inventory_workbook(remembered_paths["inventory"])
    controller.set_barcode_folder(remembered_paths["barcodes"])
    controller.set_label_folder(remembered_paths["label_folder"])
    controller.set_label_filename("Test Labels Carrie.xlsx")

    loaded = load_gui_preferences(path=preferences_path)
    assert loaded.inventory_workbook == remembered_paths["inventory"].resolve()
    assert loaded.barcode_folder == remembered_paths["barcodes"].resolve()
    assert loaded.label_folder == remembered_paths["label_folder"].resolve()
    assert loaded.label_filename == "Test Labels Carrie.xlsx"
    window.close()
