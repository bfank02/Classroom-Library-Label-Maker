"""GUI controller — owns form state and starts background generation.

Responsibilities:

* own :class:`GenerationFormState`
* handle browse / template / generate actions
* update path labels and control enablement
* lightweight form validation
* construct :class:`ApplicationSettings` and start a :class:`GenerationWorker`
* display engine progress / success / success-with-warnings / failure in the
  status line

Does **not** implement ISBN / import / barcode / layout logic or cancellation.
``WorkbookGenerationService`` remains Qt-unaware.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, Slot
from PySide6.QtWidgets import QFileDialog

from classroom_library_label_maker.config import load_application_settings
from classroom_library_label_maker.exceptions import ApplicationError
from classroom_library_label_maker.gui.form_state import GenerationFormState
from classroom_library_label_maker.gui.generation_worker import (
    GenerationJob,
    GenerationServiceFactory,
    GenerationWorker,
    WorkbookGenerator,
    _default_generation_service,
)
from classroom_library_label_maker.gui_preferences import (
    GuiPreferences,
    default_gui_preferences_path,
    load_gui_preferences,
    save_gui_preferences,
    usable_barcode_folder,
    usable_output_workbook,
)
from classroom_library_label_maker.label_templates import (
    LabelTemplate,
    TemplateRegistry,
    create_default_template_registry,
)
from classroom_library_label_maker.generation_summary import gui_completion_status
from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.models import (
    ApplicationSettings,
    LabelContentOptions,
    WorkbookGenerationResult,
)
from classroom_library_label_maker.progress import GenerationProgress
from classroom_library_label_maker.user_paths import (
    barcode_folder_dialog_start_directory,
    inventory_dialog_start_directory,
    label_workbook_save_dialog_defaults,
)

if TYPE_CHECKING:
    from classroom_library_label_maker.gui.main_window import MainWindow

OpenFileDialog = Callable[[], Path | None]
OpenDirDialog = Callable[[], Path | None]
SaveFileDialog = Callable[[], Path | None]

# Re-export for existing tests / callers.
__all__ = [
    "GenerationServiceFactory",
    "GuiController",
    "WorkbookGenerator",
    "ensure_excel_workbook_suffix",
    "template_display_name",
]


def template_display_name(template: LabelTemplate) -> str:
    """Return a short combo-box label (e.g. ``Avery 5160``)."""
    vendor = template.vendor.strip()
    product = template.product_number.strip()
    if vendor and product:
        return f"{vendor} {product}"
    return template.template_name


class GuiController(QObject):
    """Connects the main window to presentation-layer form state and generation.

    Subclasses :class:`QObject` so worker ``completed`` / ``failed`` signals are
    delivered on the GUI thread via queued connections.
    """

    def __init__(
        self,
        window: MainWindow,
        *,
        template_registry: TemplateRegistry | None = None,
        open_inventory_dialog: OpenFileDialog | None = None,
        open_barcode_folder_dialog: OpenDirDialog | None = None,
        save_output_dialog: SaveFileDialog | None = None,
        generation_service_factory: GenerationServiceFactory | None = None,
        preferences_path: Path | None = None,
    ) -> None:
        super().__init__(window)
        self._window = window
        self._logger = get_logger("gui")
        self._registry = template_registry or create_default_template_registry()
        self._open_inventory_dialog = open_inventory_dialog or self._default_open_inventory
        self._open_barcode_folder_dialog = (
            open_barcode_folder_dialog or self._default_open_barcode_folder
        )
        self._save_output_dialog = save_output_dialog or self._default_save_output
        self._generation_service_factory = (
            generation_service_factory or _default_generation_service
        )
        self._preferences_path = preferences_path
        self._state = GenerationFormState()
        self._is_generating = False
        self._active_thread: QThread | None = None
        self._active_worker: GenerationWorker | None = None

        self._populate_templates()
        self._restore_preferences()
        self._connect_signals()
        self._refresh_ui()

    @property
    def state(self) -> GenerationFormState:
        """Current form selections (immutable snapshot)."""
        return self._state

    @property
    def is_generating(self) -> bool:
        """True while a background generation job is in progress."""
        return self._is_generating

    def set_inventory_workbook(self, path: Path | None) -> None:
        """Update the inventory workbook selection and refresh the UI."""
        self._state = self._state.with_inventory_workbook(
            path.resolve() if path is not None else None
        )
        self._refresh_ui()

    def set_barcode_folder(self, path: Path | None) -> None:
        """Update the barcode folder selection, remember it, and refresh the UI."""
        self._state = self._state.with_barcode_folder(
            path.resolve() if path is not None else None
        )
        self._persist_preferences()
        self._refresh_ui()

    def set_output_workbook(self, path: Path | None) -> None:
        """Update the output workbook path, remember it, and refresh the UI."""
        self._state = self._state.with_output_workbook(
            path.resolve() if path is not None else None
        )
        self._persist_preferences()
        self._refresh_ui()

    def set_label_template_id(self, template_id: str | None) -> None:
        """Update the selected label template id and refresh the UI."""
        cleaned = template_id.strip() if template_id else None
        self._state = self._state.with_label_template_id(cleaned or None)
        self._refresh_ui()

    def set_label_content(self, content: LabelContentOptions) -> None:
        """Update which fields appear on labels and refresh the UI."""
        self._state = self._state.with_label_content(content)
        self._refresh_ui()

    def on_label_content_changed(self) -> None:
        """Handle Show on labels checkbox changes."""
        if self._is_generating:
            return
        window = self._window
        content = LabelContentOptions(
            show_title=window.show_title_checkbox.isChecked(),
            show_author=window.show_author_checkbox.isChecked(),
            show_barcode=window.show_barcode_checkbox.isChecked(),
        )
        self.set_label_content(content)

    def browse_inventory_workbook(self) -> None:
        """Open a native file dialog for the inventory workbook."""
        if self._is_generating:
            return
        selected = self._open_inventory_dialog()
        if selected is not None:
            self.set_inventory_workbook(selected)

    def browse_barcode_folder(self) -> None:
        """Open a native folder dialog for barcode PNG output."""
        if self._is_generating:
            return
        selected = self._open_barcode_folder_dialog()
        if selected is not None:
            self.set_barcode_folder(selected)

    def browse_output_workbook(self) -> None:
        """Open a native save dialog for the label workbook."""
        if self._is_generating:
            return
        selected = self._save_output_dialog()
        if selected is not None:
            self.set_output_workbook(selected)

    def on_template_changed(self, index: int) -> None:
        """Handle label-template combo selection changes."""
        if self._is_generating:
            return
        if index < 0:
            self.set_label_template_id(None)
            return
        template_id = self._window.label_template_combo.itemData(index)
        if isinstance(template_id, str):
            self.set_label_template_id(template_id)
        else:
            self.set_label_template_id(None)

    def build_application_settings(self) -> ApplicationSettings:
        """Build settings for generation from the validated form state.

        Raises:
            ApplicationError: When required form fields are missing.
        """
        messages = self._state.validation_messages()
        if messages:
            raise ApplicationError(messages[0])

        inventory = self._state.inventory_workbook
        barcodes = self._state.barcode_folder
        template_id = self._state.label_template_id
        assert inventory is not None
        assert barcodes is not None
        assert template_id is not None

        return load_application_settings(
            workbook_path=inventory,
            barcode_output_directory=barcodes,
            label_template_id=template_id,
            label_content=self._state.label_content,
            overwrite=False,
        )

    def on_generate_labels(self) -> None:
        """Validate the form and start background workbook generation."""
        if self._is_generating:
            return

        messages = self._state.validation_messages()
        if messages:
            self._set_status(" ".join(messages), level="error")
            self._window.generate_button.setEnabled(False)
            return

        inventory = self._state.inventory_workbook
        output = self._state.output_workbook
        assert inventory is not None
        assert output is not None

        try:
            settings = self.build_application_settings()
        except ApplicationError as exc:
            self._set_status(exc.message, level="error")
            self._window.generate_button.setEnabled(False)
            return

        job = GenerationJob(
            settings=settings,
            workbook_path=inventory,
            output_path=output,
        )
        self._logger.info(
            "Running generate via WorkbookGenerationService "
            "(inventory=%s, barcodes=%s, output=%s, template=%s)",
            inventory,
            settings.barcode_output_directory,
            output,
            settings.label_template_id,
        )

        self._is_generating = True
        self._set_inputs_enabled(False)
        self._set_status("Generating labels…", level="ok")

        thread = QThread()
        worker = GenerationWorker(
            job,
            service_factory=self._generation_service_factory,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_generation_progress)
        worker.completed.connect(self._on_generation_completed)
        worker.failed.connect(self._on_generation_failed)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(self._on_generation_thread_finished)

        self._active_thread = thread
        self._active_worker = worker
        thread.start()

    @Slot(object)
    def _on_generation_progress(self, progress: object) -> None:
        if not self._is_generating:
            return
        if not isinstance(progress, GenerationProgress):
            return
        self._set_status(progress.message, level="ok")

    @Slot(object)
    def _on_generation_completed(self, result: object) -> None:
        assert isinstance(result, WorkbookGenerationResult)
        self._is_generating = False
        self._logger.info(
            "Generation complete: %s",
            result.to_dict()["summary"],
        )
        level = "warning" if result.requires_review else "ok"
        self._set_status(gui_completion_status(result), level=level)
        self._set_inputs_enabled(True)

    @Slot(object)
    def _on_generation_failed(self, exc: object) -> None:
        self._is_generating = False
        if isinstance(exc, ApplicationError):
            self._logger.error("%s", exc)
            if exc.__cause__ is not None:
                self._logger.debug(
                    "Caused by: %s",
                    exc.__cause__,
                    exc_info=exc.__cause__,
                )
            self._set_status(exc.message, level="error")
        else:
            self._logger.error(
                "Unhandled error during workbook generation",
                exc_info=exc if isinstance(exc, BaseException) else False,
            )
            self._set_status(
                "Something went wrong while generating labels. "
                "Check the log for details.",
                level="error",
            )
        self._set_inputs_enabled(True)

    @Slot()
    def _on_generation_thread_finished(self) -> None:
        """Drop worker/thread references after the background thread stops."""
        worker = self._active_worker
        thread = self._active_thread
        self._active_worker = None
        self._active_thread = None
        if worker is not None:
            worker.deleteLater()
        if thread is not None:
            thread.deleteLater()

    def _set_inputs_enabled(self, enabled: bool) -> None:
        window = self._window
        window.inventory_browse_button.setEnabled(enabled)
        window.barcode_browse_button.setEnabled(enabled)
        window.output_browse_button.setEnabled(enabled)
        window.label_template_combo.setEnabled(enabled)
        window.show_title_checkbox.setEnabled(enabled)
        window.show_author_checkbox.setEnabled(enabled)
        window.show_barcode_checkbox.setEnabled(enabled)
        if enabled:
            window.generate_button.setEnabled(self._state.is_valid)
        else:
            window.generate_button.setEnabled(False)

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
        window.show_title_checkbox.toggled.connect(self.on_label_content_changed)
        window.show_author_checkbox.toggled.connect(self.on_label_content_changed)
        window.show_barcode_checkbox.toggled.connect(self.on_label_content_changed)
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
        self._sync_content_checkboxes()

        if self._is_generating:
            self._set_inputs_enabled(False)
            return

        messages = self._state.validation_messages()
        self._set_inputs_enabled(True)
        if messages:
            self._set_status(messages[0], level="error")
        else:
            self._set_status("Ready to generate labels.", level="ok")

    def _sync_content_checkboxes(self) -> None:
        content = self._state.label_content
        window = self._window
        for checkbox, checked in (
            (window.show_title_checkbox, content.show_title),
            (window.show_author_checkbox, content.show_author),
            (window.show_barcode_checkbox, content.show_barcode),
        ):
            if checkbox.isChecked() != checked:
                checkbox.blockSignals(True)
                checkbox.setChecked(checked)
                checkbox.blockSignals(False)

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

    def _set_status(self, message: str, *, level: str) -> None:
        """Update the status label.

        ``level`` is one of ``ok``, ``warning``, or ``error``. Warning is used
        for completed runs that still require review before printing.
        """
        self._window.status_label.setText(message)
        self._window.status_label.setProperty("statusLevel", level)
        self._window.status_label.setProperty("error", level == "error")
        colors = {
            "ok": "#0b6a0b",
            "warning": "#9a6700",
            "error": "#a1260d",
        }
        color = colors.get(level, colors["ok"])
        self._window.status_label.setStyleSheet(f"color: {color};")

    def _preferences_file(self) -> Path:
        if self._preferences_path is not None:
            return self._preferences_path
        return default_gui_preferences_path()

    def _restore_preferences(self) -> None:
        """Seed barcode folder and label workbook from remembered paths."""
        preferences = load_gui_preferences(path=self._preferences_file())
        barcode = usable_barcode_folder(preferences.barcode_folder)
        output = usable_output_workbook(preferences.output_workbook)
        if barcode is not None:
            self._state = self._state.with_barcode_folder(barcode)
        if output is not None:
            self._state = self._state.with_output_workbook(output)

    def _persist_preferences(self) -> None:
        """Write current barcode / label paths for the next launch."""
        try:
            save_gui_preferences(
                GuiPreferences(
                    barcode_folder=self._state.barcode_folder,
                    output_workbook=self._state.output_workbook,
                ),
                path=self._preferences_file(),
            )
        except OSError as exc:
            self._logger.warning("Could not save path preferences: %s", exc)

    def _default_open_inventory(self) -> Path | None:
        path, _filter = QFileDialog.getOpenFileName(
            self._window,
            "Choose Inventory Workbook",
            inventory_dialog_start_directory(),
            "Excel workbooks (*.xlsx *.xlsm);;All files (*.*)",
        )
        return Path(path) if path else None

    def _default_open_barcode_folder(self) -> Path | None:
        path = QFileDialog.getExistingDirectory(
            self._window,
            "Choose Barcode Folder",
            barcode_folder_dialog_start_directory(
                last_barcode_folder=self._state.barcode_folder,
            ),
        )
        return Path(path) if path else None

    def _default_save_output(self) -> Path | None:
        start_dir, suggested_name = label_workbook_save_dialog_defaults(
            last_output_workbook=self._state.output_workbook,
        )
        path, selected_filter = QFileDialog.getSaveFileName(
            self._window,
            "Save Label Workbook",
            str(Path(start_dir) / suggested_name),
            "Excel workbook (*.xlsx);;Excel macro-enabled workbook (*.xlsm)",
        )
        if not path:
            return None
        return ensure_excel_workbook_suffix(
            Path(path),
            preferred_filter=selected_filter,
        )


def ensure_excel_workbook_suffix(
    path: Path,
    *,
    preferred_filter: str = "",
) -> Path:
    """Ensure ``path`` has a sensible Excel suffix for save dialogs.

    Preserves ``.xlsx`` / ``.xlsm`` when already present. Otherwise applies
    ``.xlsm`` when the chosen filter mentions it, else ``.xlsx``.
    """
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xlsm"}:
        return path
    if "xlsm" in preferred_filter.lower():
        return path.with_suffix(".xlsm")
    return path.with_suffix(".xlsx")
