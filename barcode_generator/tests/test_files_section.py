"""Tests for Files section UX: folder + editable filename."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFocusEvent

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from classroom_library_label_maker.constants import DEFAULT_LABEL_FILENAME
from classroom_library_label_maker.gui.app import create_application
from classroom_library_label_maker.gui.controller import (
    GuiController,
    normalize_label_filename,
)
from classroom_library_label_maker.gui.form_state import (
    GenerationFormState,
    build_label_output_path,
)
from classroom_library_label_maker.gui.main_window import (
    FilenameLineEdit,
    MainWindow,
)
from classroom_library_label_maker.gui_preferences import (
    GuiPreferences,
    load_gui_preferences,
    save_gui_preferences,
)


@pytest.fixture(scope="module")
def qapp():
    app = create_application(["classroom-library-label-maker-files-section-test"])
    yield app


@pytest.fixture
def tmp_paths(tmp_path: Path) -> dict[str, Path]:
    inventory = tmp_path / "inventory.xlsx"
    inventory.write_bytes(b"PK\x03\x04")
    barcodes = tmp_path / "barcodes"
    barcodes.mkdir()
    labels = tmp_path / "labels"
    labels.mkdir()
    other = tmp_path / "other-labels"
    other.mkdir()
    return {
        "inventory": inventory,
        "barcodes": barcodes,
        "labels": labels,
        "other": other,
        "output": labels / "library_labels.xlsx",
    }


def test_build_label_output_path() -> None:
    folder = Path("/tmp/labels")
    assert build_label_output_path(folder, "Test.xlsx") == folder / "Test.xlsx"
    assert build_label_output_path(None, "Test.xlsx") is None
    assert build_label_output_path(folder, "  ") is None


def test_normalize_label_filename_adds_xlsx() -> None:
    assert normalize_label_filename("Test Labels Carrie") == "Test Labels Carrie.xlsx"
    assert normalize_label_filename("Test.xlsm") == "Test.xlsm"
    assert normalize_label_filename("nested/path/book.xlsx") == "book.xlsx"
    assert normalize_label_filename("   ") == ""


def test_filename_stem_selection(qapp) -> None:
    edit = FilenameLineEdit("Test Labels Carrie.xlsx")
    edit.select_filename_stem()
    assert edit.selectedText() == "Test Labels Carrie"
    edit.setText("book.xlsm")
    edit.select_filename_stem()
    assert edit.selectedText() == "book"


def test_filename_focus_selects_stem(qapp) -> None:
    window = MainWindow()
    edit = window.filename_edit
    edit.setText("My Labels.xlsx")
    edit.setFocus()
    # Simulate focus-in selection (offscreen focus can be unreliable).
    edit.focusInEvent(QFocusEvent(QFocusEvent.Type.FocusIn, Qt.FocusReason.MouseFocusReason))
    assert edit.selectedText() == "My Labels"
    window.close()


def test_browse_label_folder_preserves_filename(qapp, tmp_paths: dict[str, Path]) -> None:
    window = MainWindow()
    controller = GuiController(
        window,
        open_label_folder_dialog=lambda: tmp_paths["other"],
    )
    controller.set_label_folder(tmp_paths["labels"])
    controller.set_label_filename("Test Labels Carrie.xlsx")
    original_name = controller.state.label_filename

    controller.browse_label_folder()

    assert controller.state.label_folder == tmp_paths["other"].resolve()
    assert controller.state.label_filename == original_name
    assert controller.state.output_workbook == (
        tmp_paths["other"].resolve() / "Test Labels Carrie.xlsx"
    )
    window.close()


def test_filename_editing_updates_state_and_output_path(
    qapp, tmp_paths: dict[str, Path]
) -> None:
    window = MainWindow()
    controller = GuiController(window)
    controller.set_label_folder(tmp_paths["labels"])
    window.filename_edit.setText("Carrie Class")
    controller.on_filename_editing_finished()

    assert controller.state.label_filename == "Carrie Class.xlsx"
    assert window.filename_edit.text() == "Carrie Class.xlsx"
    assert controller.state.output_workbook == tmp_paths["labels"].resolve() / (
        "Carrie Class.xlsx"
    )
    window.close()


def test_validation_requires_filename_and_folder(tmp_paths: dict[str, Path]) -> None:
    state = GenerationFormState(
        inventory_workbook=tmp_paths["inventory"],
        barcode_folder=tmp_paths["barcodes"],
        label_folder=None,
        label_filename=DEFAULT_LABEL_FILENAME,
        label_template_id="avery-5160",
    )
    assert any("label folder" in m.lower() for m in state.validation_messages())

    state = state.with_label_folder(tmp_paths["labels"]).with_label_filename("")
    assert any("file name" in m.lower() for m in state.validation_messages())

    state = state.with_label_filename("bad:name.xlsx")
    assert any("invalid characters" in m.lower() for m in state.validation_messages())


def test_path_labels_remain_text_selectable(qapp) -> None:
    window = MainWindow()
    flags = window.inventory_path_label.textInteractionFlags()
    assert flags & Qt.TextInteractionFlag.TextSelectableByMouse
    assert flags & Qt.TextInteractionFlag.TextSelectableByKeyboard
    window.close()


def test_files_section_accessibility_names(qapp) -> None:
    window = MainWindow()
    assert window.inventory_browse_button.accessibleName() == (
        "Browse for inventory workbook"
    )
    assert window.barcode_browse_button.accessibleName() == "Browse for barcode folder"
    assert window.output_browse_button.accessibleName() == "Browse for label folder"
    assert window.filename_edit.accessibleName() == "Label File Name"
    assert window.inventory_path_label.accessibleName() == "Selected inventory workbook"
    assert window.barcode_path_label.accessibleName() == "Selected barcode folder"
    assert window.output_path_label.accessibleName() == "Selected label folder"
    window.close()


def test_persistence_of_four_file_fields(
    qapp, tmp_paths: dict[str, Path], tmp_path: Path
) -> None:
    preferences_path = tmp_path / "files.json"
    window = MainWindow()
    controller = GuiController(window, preferences_path=preferences_path)
    controller.set_inventory_workbook(tmp_paths["inventory"])
    controller.set_barcode_folder(tmp_paths["barcodes"])
    controller.set_label_folder(tmp_paths["labels"])
    controller.set_label_filename("Demo Labels.xlsx")
    window.close()

    loaded = load_gui_preferences(path=preferences_path)
    assert loaded == GuiPreferences(
        inventory_workbook=tmp_paths["inventory"].resolve(),
        barcode_folder=tmp_paths["barcodes"].resolve(),
        label_folder=tmp_paths["labels"].resolve(),
        label_filename="Demo Labels.xlsx",
        save_updated_inventory_on_review=True,
    )

    window2 = MainWindow()
    controller2 = GuiController(window2, preferences_path=preferences_path)
    assert controller2.state.inventory_workbook == tmp_paths["inventory"].resolve()
    assert controller2.state.label_filename == "Demo Labels.xlsx"
    assert "Demo Labels.xlsx" not in window2.output_path_label.text()
    assert window2.filename_edit.text() == "Demo Labels.xlsx"
    window2.close()
