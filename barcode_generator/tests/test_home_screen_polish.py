"""Tests for Home screen organization & polish (v1.4 Phase 5)."""

from __future__ import annotations

import os

from PySide6.QtWidgets import QApplication, QGroupBox
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from classroom_library_label_maker.gui.app import create_application
from classroom_library_label_maker.gui.main_window import MainWindow
from classroom_library_label_maker.metadata import APP_NAME, APP_VERSION


@pytest.fixture(scope="module")
def qapp():
    app = create_application(["classroom-library-label-maker-gui-home-polish"])
    yield app


def test_home_sections_layout(qapp) -> None:
    window = MainWindow()
    window.show()
    QApplication.processEvents()

    files = window.findChild(QGroupBox, "filesGroup")
    options = window.findChild(QGroupBox, "optionsGroup")
    actions = window.findChild(QGroupBox, "actionsGroup")
    assert files is not None
    assert options is not None
    assert actions is not None
    assert files.title() == "Files"
    assert options.title() == "Options"
    assert actions.title() == "Actions"
    assert files.accessibleName() == "Files"
    assert options.accessibleName() == "Options"
    assert actions.accessibleName() == "Actions"

    # Top-to-bottom: Files before Options before Actions.
    assert files.y() < options.y() < actions.y()
    window.close()


def test_application_header(qapp) -> None:
    window = MainWindow()
    window.show()
    QApplication.processEvents()

    assert window.header_title_label.text() == APP_NAME
    assert "classroom library" in window.header_subtitle_label.text().lower()
    assert window.findChild(object, "homeHeader") is not None
    window.close()


def test_version_display(qapp) -> None:
    window = MainWindow()
    window.show()
    QApplication.processEvents()

    assert window.version_label.text() == f"Version {APP_VERSION}"
    assert APP_VERSION in window.version_label.text()
    assert window.version_label.accessibleName() == "Application version"
    window.close()


def test_generate_button_in_actions_section(qapp) -> None:
    window = MainWindow()
    window.show()
    QApplication.processEvents()

    actions = window.findChild(QGroupBox, "actionsGroup")
    assert actions is not None
    assert window.generate_button.parentWidget() is not None
    # Generate lives under the Actions section hierarchy.
    parent = window.generate_button.parentWidget()
    ancestors = []
    while parent is not None:
        ancestors.append(parent)
        parent = parent.parentWidget()
    assert actions in ancestors
    assert window.generate_button.minimumHeight() >= 40
    assert window.generate_button.minimumWidth() >= 200
    window.close()


def test_status_belongs_to_actions_section(qapp) -> None:
    window = MainWindow()
    window.show()
    QApplication.processEvents()

    actions = window.findChild(QGroupBox, "actionsGroup")
    files = window.findChild(QGroupBox, "filesGroup")
    assert actions is not None
    assert files is not None

    parent = window.status_label.parentWidget()
    ancestors = []
    while parent is not None:
        ancestors.append(parent)
        parent = parent.parentWidget()
    assert actions in ancestors
    assert files not in ancestors
    assert window.status_label.y() < window.generate_button.y()
    window.close()


def test_home_accessibility_names(qapp) -> None:
    window = MainWindow()
    window.show()
    QApplication.processEvents()

    assert window.accessibleName() == APP_NAME
    assert window.header_title_label.accessibleName() == APP_NAME
    assert window.header_subtitle_label.accessibleName() == "Application description"
    assert window.status_label.accessibleName() == "Status"
    assert window.generate_button.accessibleName() == "Generate Labels"
    assert window.inventory_browse_button.accessibleName()
    assert window.filename_edit.accessibleName() == "Label File Name"
    assert window.findChild(object, "escapeCloseShortcut") is not None
    window.close()
