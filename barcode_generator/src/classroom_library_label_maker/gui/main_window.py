"""Primary application window — input collection layout only.

Widgets and layout live here. Form state, validation, and user actions are
owned by :class:`~classroom_library_label_maker.gui.controller.GuiController`.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
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

from classroom_library_label_maker.metadata import APP_NAME, APP_VERSION


class MainWindow(QMainWindow):
    """Top-level window for collecting generation inputs."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setMinimumSize(560, 360)
        self.resize(720, 420)

        central = QWidget(self)
        central.setObjectName("centralWidget")
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
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
            browse_tooltip="Choose the Excel inventory workbook to import.",
            path_accessible="Selected inventory workbook path",
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
            browse_tooltip="Choose the folder where barcode PNG files are stored.",
            path_accessible="Selected barcode folder path",
        )
        (
            self.output_label,
            self.output_browse_button,
            self.output_path_label,
        ) = self._add_path_row(
            form,
            mnemonic="&Output workbook:",
            browse_name="outputBrowseButton",
            path_name="outputPathLabel",
            browse_tooltip="Choose where to save the label workbook.",
            path_accessible="Selected output workbook path",
        )

        self.template_label = QLabel("&Label template:")
        self.template_label.setObjectName("labelTemplateLabel")
        self.label_template_combo = QComboBox()
        self.label_template_combo.setObjectName("labelTemplateCombo")
        self.label_template_combo.setMinimumWidth(220)
        self.label_template_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.label_template_combo.setToolTip("Label sheet layout used for placement.")
        self.label_template_combo.setAccessibleName("Label template")
        self.template_label.setBuddy(self.label_template_combo)
        form.addRow(self.template_label, self.label_template_combo)

        root.addLayout(form)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.status_label.setMinimumHeight(40)
        self.status_label.setAccessibleName("Validation status")
        root.addWidget(self.status_label)

        root.addStretch(1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.generate_button = QPushButton("&Generate Labels")
        self.generate_button.setObjectName("generateButton")
        self.generate_button.setEnabled(False)
        self.generate_button.setDefault(True)
        self.generate_button.setMinimumWidth(160)
        self.generate_button.setToolTip(
            "Validate inputs and prepare to generate labels "
            "(generation is not connected yet)."
        )
        self.generate_button.setAccessibleName("Generate Labels")
        button_row.addWidget(self.generate_button)
        button_row.addStretch(1)
        root.addLayout(button_row)

        self.setCentralWidget(central)
        self._set_tab_order()

    def _add_path_row(
        self,
        form: QFormLayout,
        *,
        mnemonic: str,
        browse_name: str,
        path_name: str,
        browse_tooltip: str,
        path_accessible: str,
    ) -> tuple[QLabel, QPushButton, QLabel]:
        label = QLabel(mnemonic)
        browse = QPushButton("Browse…")
        browse.setObjectName(browse_name)
        browse.setToolTip(browse_tooltip)
        browse.setAccessibleName(browse_tooltip)
        browse.setAutoDefault(False)

        path = QLabel("No selection")
        path.setObjectName(path_name)
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path.setWordWrap(True)
        path.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        path.setAccessibleName(path_accessible)
        path.setToolTip("No selection")

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
