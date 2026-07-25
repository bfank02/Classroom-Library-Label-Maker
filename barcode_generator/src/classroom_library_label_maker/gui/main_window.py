"""Primary application window shell.

UI widgets belong here. Generation orchestration belongs in the controller
(and ultimately ``WorkbookGenerationService``) — not in this module.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from classroom_library_label_maker.metadata import APP_NAME, APP_VERSION


class MainWindow(QMainWindow):
    """Top-level window for Classroom Library Label Maker."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setMinimumSize(640, 400)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        placeholder = QLabel(
            "Desktop shell ready.\n"
            "Workbook generation UI will be wired in a later RC3 step."
        )
        placeholder.setObjectName("guiPlaceholderLabel")
        layout.addWidget(placeholder)
        self.setCentralWidget(central)
