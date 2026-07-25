"""Tests for RC3.5 product polish helpers and wording."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtTest import QTest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from classroom_library_label_maker.gui.app import create_application
from classroom_library_label_maker.gui.controller import ensure_excel_workbook_suffix
from classroom_library_label_maker.gui.form_state import GenerationFormState
from classroom_library_label_maker.gui.icons import (
    load_application_icon,
    resolve_application_icon_path,
)
from classroom_library_label_maker.gui.main_window import MainWindow
from classroom_library_label_maker.metadata import APP_NAME


@pytest.fixture(scope="module")
def qapp():
    app = create_application(["classroom-library-label-maker-gui-polish-test"])
    yield app


def test_ensure_excel_suffix_preserves_existing() -> None:
    assert ensure_excel_workbook_suffix(Path("a.xlsx")) == Path("a.xlsx")
    assert ensure_excel_workbook_suffix(Path("a.xlsm")) == Path("a.xlsm")


def test_ensure_excel_suffix_adds_default_xlsx() -> None:
    assert ensure_excel_workbook_suffix(Path("labels")) == Path("labels.xlsx")


def test_ensure_excel_suffix_honors_xlsm_filter() -> None:
    assert (
        ensure_excel_workbook_suffix(
            Path("labels"),
            preferred_filter="Excel macro-enabled workbook (*.xlsm)",
        )
        == Path("labels.xlsm")
    )


def test_validation_messages_are_actionable() -> None:
    messages = GenerationFormState().validation_messages()
    assert messages[0].startswith("Choose ")
    assert all("Traceback" not in message for message in messages)


def test_window_title_uses_product_name(qapp) -> None:
    window = MainWindow()
    assert window.windowTitle() == APP_NAME
    assert window.findChild(object, "closeWindowAction") is not None
    window.close()


def test_escape_closes_window(qapp) -> None:
    window = MainWindow()
    window.show()
    QTest.qWait(20)
    shortcut = window.findChild(object, "escapeCloseShortcut")
    assert shortcut is not None
    shortcut.activated.emit()
    QTest.qWait(20)
    assert not window.isVisible()
    window.close()


def test_empty_icon_placeholders_are_ignored() -> None:
    path = resolve_application_icon_path()
    assert path is None  # assets currently ship empty placeholders
    assert load_application_icon().isNull()
