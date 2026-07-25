"""GUI controller — owns form state and user-input actions.

Responsibilities for this milestone:

* own :class:`GenerationFormState`
* handle browse / template / generate actions
* update path labels and Generate enablement
* lightweight validation with user-friendly messages

Does **not** invoke ``WorkbookGenerationService``, start threads, or report
progress. Generate confirms that generation *would* begin.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFileDialog, QMessageBox

from classroom_library_label_maker.gui.form_state import GenerationFormState
from classroom_library_label_maker.label_templates import (
    LabelTemplate,
    TemplateRegistry,
    create_default_template_registry,
)
from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.metadata import APP_NAME

if TYPE_CHECKING:
    from classroom_library_label_maker.gui.main_window import MainWindow

OpenFileDialog = Callable[[], Path | None]
OpenDirDialog = Callable[[], Path | None]
SaveFileDialog = Callable[[], Path | None]


def template_display_name(template: LabelTemplate) -> str:
    """Return a short combo-box label (e.g. ``Avery 5160``)."""
    vendor = template.vendor.strip()
    product = template.product_number.strip()
    if vendor and product:
        return f"{vendor} {product}"
    return template.template_name


class GuiController:
    """Connects the main window to presentation-layer form state."""

    def __init__(
        self,
        window: MainWindow,
        *,
        template_registry: TemplateRegistry | None = None,
        open_inventory_dialog: OpenFileDialog | None = None,
        open_barcode_folder_dialog: OpenDirDialog | None = None,
        save_output_dialog: SaveFileDialog | None = None,
        show_info_dialog: bool = True,
    ) -> None:
        self._window = window
        self._logger = get_logger("gui")
        self._registry = template_registry or create_default_template_registry()
        self._open_inventory_dialog = open_inventory_dialog or self._default_open_inventory
        self._open_barcode_folder_dialog = (
            open_barcode_folder_dialog or self._default_open_barcode_folder
        )
        self._save_output_dialog = save_output_dialog or self._default_save_output
        self._show_info_dialog = show_info_dialog
        self._state = GenerationFormState()

        self._populate_templates()
        self._connect_signals()
        self._refresh_ui()

    @property
    def state(self) -> GenerationFormState:
        """Current form selections (immutable snapshot)."""
        return self._state

    def set_inventory_workbook(self, path: Path | None) -> None:
        """Update the inventory workbook selection and refresh the UI."""
        self._state = self._state.with_inventory_workbook(
            path.resolve() if path is not None else None
        )
        self._refresh_ui()

    def set_barcode_folder(self, path: Path | None) -> None:
        """Update the barcode folder selection and refresh the UI."""
        self._state = self._state.with_barcode_folder(
            path.resolve() if path is not None else None
        )
        self._refresh_ui()

    def set_output_workbook(self, path: Path | None) -> None:
        """Update the output workbook path and refresh the UI."""
        self._state = self._state.with_output_workbook(
            path.resolve() if path is not None else None
        )
        self._refresh_ui()

    def set_label_template_id(self, template_id: str | None) -> None:
        """Update the selected label template id and refresh the UI."""
        cleaned = template_id.strip() if template_id else None
        self._state = self._state.with_label_template_id(cleaned or None)
        self._refresh_ui()

    def browse_inventory_workbook(self) -> None:
        """Open a native file dialog for the inventory workbook."""
        selected = self._open_inventory_dialog()
        if selected is not None:
            self.set_inventory_workbook(selected)

    def browse_barcode_folder(self) -> None:
        """Open a native folder dialog for barcode PNG output."""
        selected = self._open_barcode_folder_dialog()
        if selected is not None:
            self.set_barcode_folder(selected)

    def browse_output_workbook(self) -> None:
        """Open a native save dialog for the label workbook."""
        selected = self._save_output_dialog()
        if selected is not None:
            self.set_output_workbook(selected)

    def on_template_changed(self, index: int) -> None:
        """Handle label-template combo selection changes."""
        if index < 0:
            self.set_label_template_id(None)
            return
        template_id = self._window.label_template_combo.itemData(index)
        if isinstance(template_id, str):
            self.set_label_template_id(template_id)
        else:
            self.set_label_template_id(None)

    def on_generate_labels(self) -> None:
        """Validate the form and report that generation would begin.

        Does not call ``WorkbookGenerationService``.
        """
        messages = self._state.validation_messages()
        if messages:
            self._set_status(" ".join(messages), error=True)
            self._window.generate_button.setEnabled(False)
            return

        summary = (
            "Generation would begin with:\n"
            f"  inventory: {self._state.inventory_workbook}\n"
            f"  barcodes:  {self._state.barcode_folder}\n"
            f"  output:    {self._state.output_workbook}\n"
            f"  template:  {self._state.label_template_id}"
        )
        self._logger.info("%s", summary.replace("\n", " | "))
        self._set_status(
            "Inputs look good. Workbook generation is not connected yet.",
            error=False,
        )
        if self._show_info_dialog:
            QMessageBox.information(
                self._window,
                APP_NAME,
                "Generation would begin.\n\n"
                "Workbook generation is not connected in this release.",
            )

    def _populate_templates(self) -> None:
        combo = self._window.label_template_combo
        combo.blockSignals(True)
        combo.clear()
        templates = self._registry.list_templates()
        for template in templates:
            combo.addItem(template_display_name(template), template.template_id)
        combo.blockSignals(False)
        if templates:
            self._state = self._state.with_label_template_id(templates[0].template_id)
            combo.setCurrentIndex(0)

    def _connect_signals(self) -> None:
        window = self._window
        window.inventory_browse_button.clicked.connect(self.browse_inventory_workbook)
        window.barcode_browse_button.clicked.connect(self.browse_barcode_folder)
        window.output_browse_button.clicked.connect(self.browse_output_workbook)
        window.label_template_combo.currentIndexChanged.connect(self.on_template_changed)
        window.generate_button.clicked.connect(self.on_generate_labels)

    def _refresh_ui(self) -> None:
        self._set_path_label(
            self._window.inventory_path_label,
            self._state.inventory_workbook,
            empty="No file selected",
        )
        self._set_path_label(
            self._window.barcode_path_label,
            self._state.barcode_folder,
            empty="No folder selected",
        )
        self._set_path_label(
            self._window.output_path_label,
            self._state.output_workbook,
            empty="No file selected",
        )
        self._sync_template_combo()

        messages = self._state.validation_messages()
        self._window.generate_button.setEnabled(not messages)
        if messages:
            self._set_status(messages[0], error=True)
        else:
            self._set_status("Ready to generate labels.", error=False)

    def _sync_template_combo(self) -> None:
        combo = self._window.label_template_combo
        template_id = self._state.label_template_id
        if not template_id:
            return
        index = combo.findData(template_id)
        if index >= 0 and combo.currentIndex() != index:
            combo.blockSignals(True)
            combo.setCurrentIndex(index)
            combo.blockSignals(False)

    def _set_path_label(
        self,
        label: object,
        path: Path | None,
        *,
        empty: str,
    ) -> None:
        from PySide6.QtWidgets import QLabel

        assert isinstance(label, QLabel)
        if path is None:
            label.setText(empty)
            label.setToolTip(empty)
        else:
            text = str(path)
            label.setText(text)
            label.setToolTip(text)

    def _set_status(self, message: str, *, error: bool) -> None:
        self._window.status_label.setText(message)
        self._window.status_label.setProperty("error", error)
        # Keep color subtle via stylesheet property for future theming.
        color = "#a1260d" if error else "#0b6a0b"
        self._window.status_label.setStyleSheet(f"color: {color};")

    def _default_open_inventory(self) -> Path | None:
        path, _filter = QFileDialog.getOpenFileName(
            self._window,
            "Select Inventory Workbook",
            "",
            "Excel workbooks (*.xlsx *.xlsm);;All files (*.*)",
        )
        return Path(path) if path else None

    def _default_open_barcode_folder(self) -> Path | None:
        path = QFileDialog.getExistingDirectory(
            self._window,
            "Select Barcode Folder",
            "",
        )
        return Path(path) if path else None

    def _default_save_output(self) -> Path | None:
        path, _filter = QFileDialog.getSaveFileName(
            self._window,
            "Select Output Workbook",
            "library_labels.xlsx",
            "Excel workbooks (*.xlsx *.xlsm);;All files (*.*)",
        )
        return Path(path) if path else None
