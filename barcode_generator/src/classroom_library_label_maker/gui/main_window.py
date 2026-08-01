"""Primary application window — Home inputs and Ready to Print completion.

Widgets and layout live here. Form state, validation, and user actions are
owned by :class:`~classroom_library_label_maker.gui.controller.GuiController`.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFocusEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from classroom_library_label_maker.constants import DEFAULT_LABEL_FILENAME
from classroom_library_label_maker.gui.completion_view import CompletionView
from classroom_library_label_maker.metadata import APP_NAME

_HOME_PAGE = 0
_COMPLETION_PAGE = 1


class FilenameLineEdit(QLineEdit):
    """Line edit that selects the basename (without extension) on focus.

    Mimics Finder / Explorer rename behavior: the stem is selected so typing
    replaces the name while leaving a visible ``.xlsx`` / ``.xlsm`` suffix.
    """

    def focusInEvent(self, event: QFocusEvent) -> None:
        super().focusInEvent(event)
        self.select_filename_stem()

    def select_filename_stem(self) -> None:
        """Select only the filename stem, leaving the extension unselected."""
        text = self.text()
        if not text:
            return
        suffix = Path(text).suffix
        if suffix.lower() in {".xlsx", ".xlsm"} and len(text) > len(suffix):
            self.setSelection(0, len(text) - len(suffix))
        else:
            self.selectAll()


class MainWindow(QMainWindow):
    """Top-level window for collecting generation inputs and completion."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(560, 480)
        self.resize(720, 560)
        self.setAccessibleName(APP_NAME)

        central = QWidget(self)
        central.setObjectName("centralWidget")
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setObjectName("mainStack")
        self.home_page = self._build_home_page()
        self.completion_view = CompletionView()
        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.completion_view)
        central_layout.addWidget(self.stack)

        self.setCentralWidget(central)
        self._install_shortcuts()
        self._set_tab_order()
        self.show_home()

    def is_showing_completion(self) -> bool:
        """True when the Ready to Print page is visible."""
        return self.stack.currentIndex() == _COMPLETION_PAGE

    def show_home(self) -> None:
        """Show the normal Files / options / Generate home screen."""
        self.stack.setCurrentIndex(_HOME_PAGE)

    def show_completion(self) -> None:
        """Show the Ready to Print completion page (no Generate button)."""
        self.stack.setCurrentIndex(_COMPLETION_PAGE)

    def _build_home_page(self) -> QWidget:
        home = QWidget()
        home.setObjectName("homePage")
        root = QVBoxLayout(home)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

        files_group = QGroupBox("Files")
        files_group.setObjectName("filesGroup")
        files_group.setAccessibleName("Files")
        files_group.setAccessibleDescription(
            "Choose your inventory workbook, barcode folder, label folder, "
            "and label file name."
        )
        files_layout = QVBoxLayout(files_group)
        files_layout.setContentsMargins(12, 16, 12, 12)
        files_layout.setSpacing(0)

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
            mnemonic="&Inventory Workbook:",
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
            mnemonic="&Barcode Folder:",
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
            mnemonic="&Label Folder:",
            browse_name="outputBrowseButton",
            path_name="outputPathLabel",
            browse_accessible="Browse for label folder",
            browse_tooltip="Choose the folder where the label workbook is saved.",
            path_accessible="Selected label folder",
            empty_text="No folder selected",
        )
        (
            self.filename_label,
            self.filename_edit,
        ) = self._add_filename_row(form)

        files_layout.addLayout(form)
        root.addWidget(files_group)

        options_form = QFormLayout()
        options_form.setContentsMargins(0, 0, 0, 0)
        options_form.setHorizontalSpacing(16)
        options_form.setVerticalSpacing(14)
        options_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        options_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
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
        options_form.addRow(self.template_label, self.label_template_combo)

        self.content_label = QLabel("Show on &labels:")
        self.content_label.setObjectName("labelContentLabel")
        content_field = QWidget()
        content_layout = QHBoxLayout(content_field)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        self.show_title_checkbox = QCheckBox("Title")
        self.show_title_checkbox.setObjectName("showTitleCheckBox")
        self.show_title_checkbox.setChecked(True)
        self.show_title_checkbox.setToolTip("Print the book title on each label.")
        self.show_title_checkbox.setAccessibleName("Show title on labels")

        self.show_author_checkbox = QCheckBox("Author")
        self.show_author_checkbox.setObjectName("showAuthorCheckBox")
        self.show_author_checkbox.setChecked(True)
        self.show_author_checkbox.setToolTip("Print the author on each label.")
        self.show_author_checkbox.setAccessibleName("Show author on labels")

        self.show_barcode_checkbox = QCheckBox("Barcode")
        self.show_barcode_checkbox.setObjectName("showBarcodeCheckBox")
        self.show_barcode_checkbox.setChecked(True)
        self.show_barcode_checkbox.setToolTip(
            "Print the barcode image on each label (includes the ISBN digits). "
            "For best scanner results on laser printers, use Title + Barcode only."
        )
        self.show_barcode_checkbox.setAccessibleName("Show barcode on labels")

        for checkbox in (
            self.show_title_checkbox,
            self.show_author_checkbox,
            self.show_barcode_checkbox,
        ):
            content_layout.addWidget(checkbox)
        content_layout.addStretch(1)

        self.content_label.setBuddy(self.show_title_checkbox)
        options_form.addRow(self.content_label, content_field)

        self.lookup_missing_isbns_checkbox = QCheckBox(
            "Look up missing ISBNs automatically"
        )
        self.lookup_missing_isbns_checkbox.setObjectName(
            "lookupMissingIsbnsCheckBox"
        )
        self.lookup_missing_isbns_checkbox.setChecked(True)
        self.lookup_missing_isbns_checkbox.setToolTip(
            "When a book has no ISBN, search by title and author before "
            "generating barcodes. Uncheck to skip online lookup."
        )
        self.lookup_missing_isbns_checkbox.setAccessibleName(
            "Look up missing ISBNs automatically"
        )
        options_form.addRow("", self.lookup_missing_isbns_checkbox)

        root.addLayout(options_form)

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
            "Starts label generation using the selected workbook, folders, "
            "file name, and template."
        )
        button_row.addWidget(self.generate_button)
        button_row.addStretch(1)
        root.addLayout(button_row)
        return home

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
        browse.setMinimumWidth(96)
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

    def _add_filename_row(self, form: QFormLayout) -> tuple[QLabel, FilenameLineEdit]:
        label = QLabel("Label File &Name:")
        label.setObjectName("labelFilenameLabel")
        edit = FilenameLineEdit(DEFAULT_LABEL_FILENAME)
        edit.setObjectName("labelFilenameEdit")
        edit.setMinimumHeight(28)
        edit.setMinimumWidth(200)
        edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        edit.setToolTip(
            "Name of the label workbook file. The folder above is where it is saved."
        )
        edit.setAccessibleName("Label File Name")
        edit.setAccessibleDescription(
            "Editable filename for the label workbook. Extension is usually "
            ".xlsx. Click to rename; the extension stays visible."
        )
        edit.setClearButtonEnabled(False)
        label.setBuddy(edit)
        form.addRow(label, edit)
        return label, edit

    def _set_tab_order(self) -> None:
        QWidget.setTabOrder(self.inventory_browse_button, self.barcode_browse_button)
        QWidget.setTabOrder(self.barcode_browse_button, self.output_browse_button)
        QWidget.setTabOrder(self.output_browse_button, self.filename_edit)
        QWidget.setTabOrder(self.filename_edit, self.label_template_combo)
        QWidget.setTabOrder(self.label_template_combo, self.show_title_checkbox)
        QWidget.setTabOrder(self.show_title_checkbox, self.show_author_checkbox)
        QWidget.setTabOrder(self.show_author_checkbox, self.show_barcode_checkbox)
        QWidget.setTabOrder(self.show_barcode_checkbox, self.generate_button)
        QWidget.setTabOrder(
            self.completion_view.open_label_button,
            self.completion_view.open_inventory_button,
        )
        QWidget.setTabOrder(
            self.completion_view.open_inventory_button,
            self.completion_view.done_button,
        )
