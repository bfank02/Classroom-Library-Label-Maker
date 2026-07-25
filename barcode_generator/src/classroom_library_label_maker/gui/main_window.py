"""Primary application window — input collection layout only.

Widgets and layout live here. Form state, validation, and user actions are
owned by :class:`~classroom_library_label_maker.gui.controller.GuiController`.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from classroom_library_label_maker.metadata import APP_NAME


class MainWindow(QMainWindow):
    """Top-level window for collecting generation inputs."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(560, 380)
        self.resize(720, 440)
        self.setAccessibleName(APP_NAME)

        central = QWidget(self)
        central.setObjectName("centralWidget")
        root = QVBoxLayout(central)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(14)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        form.setFormAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        (
            self.inventory_label,
            self.inventory_browse_button,
            self.inventory_path_label,
        ) = self._add_path_row(
            form,
            mnemonic="&Inventory workbook:",
            browse_name="inventoryBrowseButton",
            path_name="inventoryPathLabel",
            browse_accessible="Browse for inventory workbook",
            browse_tooltip="Choose the Excel workbook that lists your books.",
            path_accessible="Selected inventory workbook",
            empty_text="No file selected",
        )
        (
            self.barcode_label,
            self.barcode_browse_button,
            self.barcode_path_label,
        ) = self._add_path_row(
            form,
            mnemonic="&Barcode folder:",
            browse_name="barcodeBrowseButton",
            path_name="barcodePathLabel",
            browse_accessible="Browse for barcode folder",
            browse_tooltip="Choose the folder where barcode images will be saved.",
            path_accessible="Selected barcode folder",
            empty_text="No folder selected",
        )
        (
            self.output_label,
            self.output_browse_button,
            self.output_path_label,
        ) = self._add_path_row(
            form,
            mnemonic="Label &workbook:",
            browse_name="outputBrowseButton",
            path_name="outputPathLabel",
            browse_accessible="Browse for label workbook",
            browse_tooltip="Choose where to save the printable label workbook.",
            path_accessible="Selected label workbook",
            empty_text="No file selected",
        )

        self.template_label = QLabel("Label &template:")
        self.template_label.setObjectName("labelTemplateLabel")
        self.label_template_combo = QComboBox()
        self.label_template_combo.setObjectName("labelTemplateCombo")
        self.label_template_combo.setMinimumWidth(240)
        self.label_template_combo.setMinimumHeight(28)
        self.label_template_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.label_template_combo.setToolTip(
            "Choose the label sheet size that matches your stickers."
        )
        self.label_template_combo.setAccessibleName("Label template")
        self.label_template_combo.setAccessibleDescription(
            "Label sheet layout used when placing barcodes."
        )
        self.template_label.setBuddy(self.label_template_combo)
        form.addRow(self.template_label, self.label_template_combo)

        root.addLayout(form)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.status_label.setMinimumHeight(48)
        self.status_label.setAccessibleName("Status")
        self.status_label.setAccessibleDescription(
            "Shows guidance, progress, success, and error messages."
        )
        root.addWidget(self.status_label)

        root.addStretch(1)

        button_row = QHBoxLayout()
        button_row.setSpacing(12)
        button_row.addStretch(1)
        self.generate_button = QPushButton("&Generate Labels")
        self.generate_button.setObjectName("generateButton")
        self.generate_button.setEnabled(False)
        self.generate_button.setDefault(True)
        self.generate_button.setAutoDefault(True)
        self.generate_button.setMinimumWidth(168)
        self.generate_button.setMinimumHeight(32)
        self.generate_button.setToolTip(
            "Create the printable label workbook from your selections."
        )
        self.generate_button.setAccessibleName("Generate Labels")
        self.generate_button.setAccessibleDescription(
            "Starts label generation using the selected workbook, folder, "
            "output path, and template."
        )
        button_row.addWidget(self.generate_button)
        button_row.addStretch(1)
        root.addLayout(button_row)

        self.setCentralWidget(central)
        self._install_shortcuts()
        self._set_tab_order()

    def _install_shortcuts(self) -> None:
        close_action = QAction(self)
        close_action.setObjectName("closeWindowAction")
        close_action.setShortcut(QKeySequence(Qt.Key.Key_Escape))
        close_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        close_action.triggered.connect(self.close)
        self.addAction(close_action)

        # QShortcut is more reliable for Esc across platforms than Cancel alone.
        escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        escape.setObjectName("escapeCloseShortcut")
        escape.setContext(Qt.ShortcutContext.WindowShortcut)
        escape.activated.connect(self.close)

    def _add_path_row(
        self,
        form: QFormLayout,
        *,
        mnemonic: str,
        browse_name: str,
        path_name: str,
        browse_accessible: str,
        browse_tooltip: str,
        path_accessible: str,
        empty_text: str,
    ) -> tuple[QLabel, QPushButton, QLabel]:
        label = QLabel(mnemonic)
        browse = QPushButton("Browse…")
        browse.setObjectName(browse_name)
        browse.setMinimumHeight(28)
        browse.setToolTip(browse_tooltip)
        browse.setAccessibleName(browse_accessible)
        browse.setAccessibleDescription(browse_tooltip)
        browse.setAutoDefault(False)

        path = QLabel(empty_text)
        path.setObjectName(path_name)
        path.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        path.setWordWrap(True)
        path.setMinimumWidth(200)
        path.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        path.setAccessibleName(path_accessible)
        path.setToolTip(empty_text)

        field = QWidget()
        field_layout = QHBoxLayout(field)
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(12)
        field_layout.addWidget(browse, 0)
        field_layout.addWidget(path, 1)

        label.setBuddy(browse)
        form.addRow(label, field)
        return label, browse, path

    def _set_tab_order(self) -> None:
        QWidget.setTabOrder(self.inventory_browse_button, self.barcode_browse_button)
        QWidget.setTabOrder(self.barcode_browse_button, self.output_browse_button)
        QWidget.setTabOrder(self.output_browse_button, self.label_template_combo)
        QWidget.setTabOrder(self.label_template_combo, self.generate_button)
