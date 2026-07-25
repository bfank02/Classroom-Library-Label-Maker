"""RC3 readiness tests for the desktop GUI package structure.

These tests verify import hygiene and entry points. They do not exercise
interactive widgets or workbook generation. Qt runs offscreen.
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Iterator

import pytest

# Must be set before QApplication is created in this process.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp() -> Iterator[object]:
    """Provide a shared offscreen QApplication for GUI structure tests."""
    from PySide6.QtWidgets import QApplication

    from classroom_library_label_maker.gui.app import create_application

    app = create_application(["classroom-library-label-maker-gui-test"])
    assert isinstance(app, QApplication)
    yield app


def test_gui_package_is_importable_without_starting_event_loop() -> None:
    """Importing ``gui`` must not create a QApplication."""
    from PySide6.QtWidgets import QApplication

    before = QApplication.instance()
    module = importlib.import_module("classroom_library_label_maker.gui")
    assert callable(module.main)
    assert "main" in module.__all__
    assert QApplication.instance() is before


def test_gui_main_entrypoint_is_exported() -> None:
    from classroom_library_label_maker.gui import main

    assert callable(main)


def test_gui_dunder_main_module_exists() -> None:
    """``python -m classroom_library_label_maker.gui`` has a ``__main__`` module."""
    module = importlib.import_module("classroom_library_label_maker.gui.__main__")
    assert callable(module.main)


def test_create_application_and_main_window(qapp: object) -> None:
    from classroom_library_label_maker.gui.app import create_main_window
    from classroom_library_label_maker.metadata import APP_NAME

    window = create_main_window()
    assert APP_NAME in window.windowTitle()
    assert window.findChild(object, "guiPlaceholderLabel") is not None
    window.show()
    qapp.processEvents()  # type: ignore[attr-defined]
    window.close()


def test_main_runs_event_loop_and_exits(qapp: object) -> None:
    """``main()`` builds the app, shows the window, and returns an exit code."""
    from PySide6.QtCore import QTimer

    from classroom_library_label_maker.gui import main

    QTimer.singleShot(0, qapp.quit)  # type: ignore[attr-defined]
    code = main(["classroom-library-label-maker-gui-main-test"])
    assert code == 0
