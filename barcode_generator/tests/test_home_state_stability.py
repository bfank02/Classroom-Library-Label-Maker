"""Regression: Home screen state ownership & layout stability (v1.4.2 Phase 1)."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from classroom_library_label_maker.constants import DEFAULT_LABEL_FILENAME
from classroom_library_label_maker.gui.app import create_application
from classroom_library_label_maker.gui.controller import GuiController
from classroom_library_label_maker.gui.dirty_fields import (
    FIELD_LABEL_FILENAME,
    DirtyFieldTracker,
)
from classroom_library_label_maker.gui.main_window import (
    MainWindow,
    _HOME_MIN_HEIGHT,
    _HOME_MIN_WIDTH,
)
from classroom_library_label_maker.gui_preferences import (
    GuiPreferences,
    load_gui_preferences,
    save_gui_preferences,
)


@pytest.fixture(scope="module")
def qapp():
    app = create_application(["classroom-library-label-maker-home-state"])
    yield app


@pytest.fixture
def tmp_paths(tmp_path: Path) -> dict[str, Path]:
    inventory = tmp_path / "inventory.xlsx"
    inventory.write_bytes(b"PK\x03\x04")
    barcodes = tmp_path / "barcodes"
    barcodes.mkdir()
    labels = tmp_path / "labels"
    labels.mkdir()
    return {
        "inventory": inventory,
        "barcodes": barcodes,
        "labels": labels,
        "prefs": tmp_path / "prefs.json",
    }


def _controller(tmp_paths: dict[str, Path]) -> tuple[MainWindow, GuiController]:
    window = MainWindow()
    controller = GuiController(window, preferences_path=tmp_paths["prefs"])
    controller.set_inventory_workbook(tmp_paths["inventory"])
    controller.set_barcode_folder(tmp_paths["barcodes"])
    controller.set_label_folder(tmp_paths["labels"])
    controller.set_label_filename(DEFAULT_LABEL_FILENAME)
    return window, controller


def test_dirty_field_tracker_generic() -> None:
    tracker = DirtyFieldTracker()
    assert tracker.is_dirty(FIELD_LABEL_FILENAME) is False
    tracker.mark(FIELD_LABEL_FILENAME)
    assert tracker.is_dirty(FIELD_LABEL_FILENAME) is True
    assert tracker.any_dirty() is True
    tracker.clear(FIELD_LABEL_FILENAME)
    assert tracker.any_dirty() is False
    tracker.mark("other")
    tracker.clear()
    assert tracker.any_dirty() is False


def test_filename_survives_checkbox_change(qapp, tmp_paths: dict[str, Path]) -> None:
    window, controller = _controller(tmp_paths)
    window.show()
    QApplication.processEvents()

    window.filename_edit.setText("My Custom Labels.xlsx")
    window.filename_edit.textEdited.emit("My Custom Labels.xlsx")
    QApplication.processEvents()

    window.show_title_checkbox.setChecked(False)
    QApplication.processEvents()

    assert window.filename_edit.text() == "My Custom Labels.xlsx"
    assert controller._dirty_fields.is_dirty(FIELD_LABEL_FILENAME) is True
    window.close()


def test_filename_survives_lookup_checkbox(qapp, tmp_paths: dict[str, Path]) -> None:
    window, controller = _controller(tmp_paths)
    window.show()
    QApplication.processEvents()

    window.filename_edit.setText("Lookup Safe.xlsx")
    window.filename_edit.textEdited.emit("Lookup Safe.xlsx")
    QApplication.processEvents()

    window.lookup_missing_isbns_checkbox.setChecked(False)
    QApplication.processEvents()
    window.lookup_missing_isbns_checkbox.setChecked(True)
    QApplication.processEvents()

    assert window.filename_edit.text() == "Lookup Safe.xlsx"
    window.close()


def test_filename_survives_template_change(qapp, tmp_paths: dict[str, Path]) -> None:
    window, controller = _controller(tmp_paths)
    window.show()
    QApplication.processEvents()

    window.filename_edit.setText("Template Safe.xlsx")
    window.filename_edit.textEdited.emit("Template Safe.xlsx")
    QApplication.processEvents()

    combo = window.label_template_combo
    if combo.count() > 1:
        combo.setCurrentIndex(1)
        QApplication.processEvents()
        combo.setCurrentIndex(0)
        QApplication.processEvents()

    assert window.filename_edit.text() == "Template Safe.xlsx"
    window.close()


def test_filename_survives_author_barcode_option_edits(
    qapp, tmp_paths: dict[str, Path]
) -> None:
    window, _controller_obj = _controller(tmp_paths)
    window.show()
    QApplication.processEvents()

    window.filename_edit.setText("Options Safe.xlsx")
    window.filename_edit.textEdited.emit("Options Safe.xlsx")
    QApplication.processEvents()

    window.show_author_checkbox.toggle()
    QApplication.processEvents()
    window.show_barcode_checkbox.toggle()
    QApplication.processEvents()

    assert window.filename_edit.text() == "Options Safe.xlsx"
    window.close()


def test_editing_finished_commits_and_clears_dirty(
    qapp, tmp_paths: dict[str, Path]
) -> None:
    window, controller = _controller(tmp_paths)
    window.show()
    QApplication.processEvents()

    window.filename_edit.setText("Committed Name")
    window.filename_edit.textEdited.emit("Committed Name")
    QApplication.processEvents()
    assert controller._dirty_fields.is_dirty(FIELD_LABEL_FILENAME)

    window.filename_edit.editingFinished.emit()
    QApplication.processEvents()

    assert controller._dirty_fields.is_dirty(FIELD_LABEL_FILENAME) is False
    assert controller.state.label_filename == "Committed Name.xlsx"
    assert window.filename_edit.text() == "Committed Name.xlsx"
    window.close()


def test_generate_commits_dirty_filename_before_validation(
    qapp, tmp_paths: dict[str, Path]
) -> None:
    window, controller = _controller(tmp_paths)
    window.show()
    QApplication.processEvents()

    window.filename_edit.setText("Generate Me")
    window.filename_edit.textEdited.emit("Generate Me")
    QApplication.processEvents()

    controller._commit_dirty_edits()
    assert controller.state.label_filename == "Generate Me.xlsx"
    assert controller._dirty_fields.is_dirty(FIELD_LABEL_FILENAME) is False
    window.close()


def test_preference_reload_does_not_clobber_dirty_filename(
    qapp, tmp_paths: dict[str, Path]
) -> None:
    window, controller = _controller(tmp_paths)
    window.show()
    QApplication.processEvents()

    window.filename_edit.setText("Keep Draft.xlsx")
    window.filename_edit.textEdited.emit("Keep Draft.xlsx")
    QApplication.processEvents()

    # Preferencing other fields refreshes UI; dirty filename must remain.
    controller.set_lookup_missing_isbns(False)
    QApplication.processEvents()
    assert window.filename_edit.text() == "Keep Draft.xlsx"

    save_gui_preferences(
        GuiPreferences(
            inventory_workbook=tmp_paths["inventory"],
            barcode_folder=tmp_paths["barcodes"],
            label_folder=tmp_paths["labels"],
            label_filename="From Disk.xlsx",
        ),
        path=tmp_paths["prefs"],
    )
    # Mid-session restore is intentional reset — clears dirty.
    controller._restore_preferences()
    controller._refresh_ui()
    QApplication.processEvents()
    assert controller._dirty_fields.any_dirty() is False
    assert window.filename_edit.text() == "From Disk.xlsx"
    assert load_gui_preferences(path=tmp_paths["prefs"]).label_filename == "From Disk.xlsx"
    window.close()


def test_home_minimum_size(qapp) -> None:
    window = MainWindow()
    assert window.minimumWidth() == _HOME_MIN_WIDTH
    assert window.minimumHeight() == _HOME_MIN_HEIGHT
    window.close()


def test_home_page_is_plain_widget(qapp) -> None:
    window = MainWindow()
    assert window.home_page.objectName() == "homePage"
    assert window.home_page.layout() is not None
    window.close()


def test_home_sections_do_not_overlap_at_default_size(qapp) -> None:
    window = MainWindow()
    window.show()
    window.resize(QSize(_HOME_MIN_WIDTH, _HOME_MIN_HEIGHT))
    QApplication.processEvents()

    files = window.findChild(object, "filesGroup")
    options = window.findChild(object, "optionsGroup")
    actions = window.findChild(object, "actionsGroup")
    assert files is not None and options is not None and actions is not None

    files_rect = files.geometry()
    options_rect = options.geometry()
    actions_rect = actions.geometry()
    assert files_rect.intersects(options_rect) is False
    assert options_rect.intersects(actions_rect) is False
    assert files_rect.bottom() <= options_rect.top()
    assert options_rect.bottom() <= actions_rect.top()
    window.close()


def test_home_resize_keeps_section_order(qapp) -> None:
    window = MainWindow()
    window.show()
    for size in (QSize(700, 650), QSize(900, 800), QSize(_HOME_MIN_WIDTH, _HOME_MIN_HEIGHT)):
        window.resize(size)
        QApplication.processEvents()
        files = window.findChild(object, "filesGroup")
        options = window.findChild(object, "optionsGroup")
        actions = window.findChild(object, "actionsGroup")
        assert files is not None and options is not None and actions is not None
        assert files.y() < options.y() < actions.y()
    window.close()
