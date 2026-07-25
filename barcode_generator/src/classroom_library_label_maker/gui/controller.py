"""GUI controller — presentation orchestration only.

Future responsibilities (not implemented in this shell):

* gather UI inputs
* validate required fields
* invoke ``WorkbookGenerationService``
* update progress / success / error dialogs

This module must not contain ISBN, import, barcode, or layout business logic.
It also must not import openpyxl or python-barcode.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from classroom_library_label_maker.gui.main_window import MainWindow


class GuiController:
    """Connects the main window to application services (stub for RC3 shell)."""

    def __init__(self, window: MainWindow) -> None:
        self._window = window
        # Intentionally no WorkbookGenerationService wiring yet — structure only.
