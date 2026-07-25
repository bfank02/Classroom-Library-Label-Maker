"""Qt application bootstrap for the desktop GUI.

Creates ``QApplication``, constructs the main window, and runs the event loop.
No business logic lives here.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from classroom_library_label_maker.gui.controller import GuiController
from classroom_library_label_maker.gui.icons import load_application_icon
from classroom_library_label_maker.gui.main_window import MainWindow
from classroom_library_label_maker.logger import get_logger, setup_logging
from classroom_library_label_maker.metadata import (
    APP_COMPANY,
    APP_NAME,
    APP_VERSION,
)
from classroom_library_label_maker.runtime_env import (
    default_user_log_file,
    is_frozen,
)


def create_application(argv: list[str] | None = None) -> QApplication:
    """Return a ``QApplication``, reusing an existing instance when present.

    Args:
        argv: Argument vector passed to Qt (defaults to ``sys.argv``).
    """
    existing = QApplication.instance()
    if existing is not None:
        if not isinstance(existing, QApplication):
            raise RuntimeError(
                "A QCoreApplication already exists but is not a QApplication"
            )
        return existing

    args = list(sys.argv if argv is None else argv)
    app = QApplication(args)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_COMPANY)
    icon = load_application_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    return app


def create_main_window() -> MainWindow:
    """Construct the main window and its presentation controller."""
    window = MainWindow()
    icon = QApplication.windowIcon()
    if not icon.isNull():
        window.setWindowIcon(icon)
    GuiController(window)
    return window


def configure_gui_logging() -> None:
    """Configure rotating file logs in a user-writable location."""
    log_file = default_user_log_file()
    setup_logging(
        level="INFO",
        log_file=log_file,
        console=not is_frozen(),
    )
    get_logger("gui").info(
        "Starting %s %s (log_file=%s, frozen=%s)",
        APP_NAME,
        APP_VERSION,
        log_file,
        is_frozen(),
    )


def run(argv: list[str] | None = None) -> int:
    """Create the application, show the main window, and start the event loop.

    Args:
        argv: Optional argument list for Qt.

    Returns:
        Exit code from ``QApplication.exec()``.
    """
    configure_gui_logging()
    app = create_application(argv)
    window = create_main_window()
    window.show()
    return int(app.exec())
