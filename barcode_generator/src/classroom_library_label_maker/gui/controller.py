"""GUI controller — owns form state and starts background generation.

Responsibilities:

* own :class:`GenerationFormState`
* handle browse / template / generate actions
* update path labels and control enablement
* lightweight form validation
* construct :class:`ApplicationSettings` and start a :class:`GenerationWorker`
* display engine progress / failure in the status line
* present the Ready to Print completion page after successful generation

Does **not** implement ISBN / import / barcode / layout logic or cancellation.
``WorkbookGenerationService`` remains Qt-unaware.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, QUrl, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QFileDialog

from classroom_library_label_maker.config import load_application_settings
from classroom_library_label_maker.exceptions import ApplicationError
from classroom_library_label_maker.generation_summary import (
    build_gui_completion_summary,
)
from classroom_library_label_maker.gui.form_state import GenerationFormState
from classroom_library_label_maker.gui.generation_worker import (
    GenerationJob,
    GenerationPhase,
    GenerationServiceFactory,
    GenerationWorker,
    WorkbookGenerator,
    _default_generation_service,
    _supports_phases,
)
from classroom_library_label_maker.gui.review_wizard import ReviewWizardDialog
from classroom_library_label_maker.gui_preferences import (
    GuiPreferences,
    default_gui_preferences_path,
    load_gui_preferences,
    save_gui_preferences,
    usable_barcode_folder,
    usable_inventory_workbook,
    usable_label_folder,
    usable_output_workbook,
)
from classroom_library_label_maker.label_templates import (
    LabelTemplate,
    TemplateRegistry,
    create_default_template_registry,
)
from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.models import (
    ApplicationSettings,
    Book,
    LabelContentOptions,
    ReviewSessionResult,
    WorkbookGenerationResult,
)
from classroom_library_label_maker.progress import GenerationProgress
from classroom_library_label_maker.services.book_review_service import (
    BookReviewService,
    ReviewSession,
    books_eligible_for_produce,
    books_with_review_applied,
    review_session_from_enrichment,
    review_session_from_generation_result,
    source_rows_for_books,
)
from classroom_library_label_maker.services.inventory_update_service import (
    InventoryUpdateService,
)
from classroom_library_label_maker.services.workbook_generation_service import (
    PreparedGeneration,
)
from classroom_library_label_maker.constants import DEFAULT_LABEL_FILENAME
from classroom_library_label_maker.user_paths import (
    barcode_folder_dialog_start_directory,
    default_label_filename,
    inventory_dialog_start_directory,
    label_folder_dialog_start_directory,
)

if TYPE_CHECKING:
    from classroom_library_label_maker.gui.main_window import MainWindow

OpenFileDialog = Callable[[], Path | None]
OpenDirDialog = Callable[[], Path | None]
SaveFileDialog = Callable[[], Path | None]
OpenPathHandler = Callable[[Path], None]


@dataclass(frozen=True, slots=True)
class ReviewWizardOutcome:
    """Result of a completed (accepted) review wizard run."""

    session: ReviewSession
    save_updated_inventory: bool
    review_result: ReviewSessionResult


ReviewWizardRunner = Callable[
    [ReviewSession, bool],
    ReviewWizardOutcome | None,
]

# Re-export for existing tests / callers.
__all__ = [
    "GenerationServiceFactory",
    "GuiController",
    "ReviewWizardOutcome",
    "ReviewWizardRunner",
    "WorkbookGenerator",
    "ensure_excel_workbook_suffix",
    "normalize_label_filename",
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
        open_label_folder_dialog: OpenDirDialog | None = None,
        save_output_dialog: SaveFileDialog | None = None,
        generation_service_factory: GenerationServiceFactory | None = None,
        preferences_path: Path | None = None,
        review_wizard_runner: ReviewWizardRunner | None = None,
        book_review_service: BookReviewService | None = None,
        inventory_update_service: InventoryUpdateService | None = None,
        open_path: OpenPathHandler | None = None,
    ) -> None:
        super().__init__(window)
        self._window = window
        self._logger = get_logger("gui")
        self._registry = template_registry or create_default_template_registry()
        self._open_inventory_dialog = (
            open_inventory_dialog or self._default_open_inventory
        )
        self._open_barcode_folder_dialog = (
            open_barcode_folder_dialog or self._default_open_barcode_folder
        )
        # Prefer the label-folder dialog; keep save_output_dialog for older
        # call sites that inject a full workbook path via browse_output_workbook.
        self._open_label_folder_dialog = (
            open_label_folder_dialog or self._default_open_label_folder
        )
        self._save_output_dialog = save_output_dialog
        self._generation_service_factory = (
            generation_service_factory or _default_generation_service
        )
        self._preferences_path = preferences_path
        self._review_wizard_runner = (
            review_wizard_runner or self._default_run_review_wizard
        )
        self._book_review_service = book_review_service or BookReviewService()
        self._inventory_update_service = (
            inventory_update_service or InventoryUpdateService()
        )
        self._open_path = open_path or self._default_open_path
        self._save_updated_inventory_on_review = True
        self._last_review_result: ReviewSessionResult | None = None
        self._last_manual_isbn_count: int = 0
        self._last_updated_inventory_path: Path | None = None
        self._pending_preparation: PreparedGeneration | None = None
        self._pending_review_outcome: ReviewWizardOutcome | None = None
        self._authoritative_books: tuple[Book, ...] | None = None
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
        """Update the inventory workbook selection, remember it, and refresh."""
        self._state = self._state.with_inventory_workbook(
            path.resolve() if path is not None else None
        )
        self._persist_preferences()
        self._refresh_ui()

    def set_barcode_folder(self, path: Path | None) -> None:
        """Update the barcode folder selection, remember it, and refresh the UI."""
        self._state = self._state.with_barcode_folder(
            path.resolve() if path is not None else None
        )
        self._persist_preferences()
        self._refresh_ui()

    def set_label_folder(self, path: Path | None) -> None:
        """Update the label folder only; preserve the current filename."""
        self._state = self._state.with_label_folder(
            path.resolve() if path is not None else None
        )
        self._persist_preferences()
        self._refresh_ui()

    def set_label_filename(self, filename: str) -> None:
        """Update the label filename (normalized) and remember it."""
        cleaned = normalize_label_filename(filename)
        self._state = self._state.with_label_filename(
            cleaned if cleaned else DEFAULT_LABEL_FILENAME
        )
        self._persist_preferences()
        self._refresh_ui()

    def set_output_workbook(self, path: Path | None) -> None:
        """Update folder + filename from a full path (tests / migration)."""
        if path is None:
            self._state = self._state.with_output_workbook(None)
        else:
            resolved = path.resolve()
            self._state = self._state.with_output_workbook(resolved)
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

    def set_lookup_missing_isbns(self, enabled: bool) -> None:
        """Update whether missing ISBNs are looked up during generation."""
        self._state = self._state.with_lookup_missing_isbns(enabled)
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

    def on_lookup_missing_isbns_changed(self) -> None:
        """Handle Look up missing ISBNs checkbox changes."""
        if self._is_generating:
            return
        self.set_lookup_missing_isbns(
            self._window.lookup_missing_isbns_checkbox.isChecked()
        )

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

    def browse_label_folder(self) -> None:
        """Open a native folder dialog for the label workbook folder.

        Preserves the filename already entered in the Files section.
        """
        if self._is_generating:
            return
        selected = self._open_label_folder_dialog()
        if selected is not None:
            self.set_label_folder(selected)

    def browse_output_workbook(self) -> None:
        """Browse for label output.

        Uses an injected full-path save dialog when provided (tests); otherwise
        opens the label-folder dialog and preserves the current filename.
        """
        if self._is_generating:
            return
        if self._save_output_dialog is not None:
            selected = self._save_output_dialog()
            if selected is not None:
                self.set_output_workbook(selected)
            return
        self.browse_label_folder()

    def on_filename_editing_finished(self) -> None:
        """Normalize and apply the label filename when editing finishes."""
        if self._is_generating:
            return
        self.set_label_filename(self._window.filename_edit.text())

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
            lookup_missing_isbns=self._state.lookup_missing_isbns,
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

        probe = self._generation_service_factory(settings)
        use_phases = _supports_phases(probe)
        phase = GenerationPhase.PREPARE if use_phases else GenerationPhase.FULL
        job = GenerationJob(
            settings=settings,
            workbook_path=inventory,
            output_path=output,
            phase=phase,
        )
        self._logger.info(
            "Running generate via WorkbookGenerationService "
            "(phase=%s, inventory=%s, barcodes=%s, output=%s, template=%s)",
            phase.value,
            inventory,
            settings.barcode_output_directory,
            output,
            settings.label_template_id,
        )

        self._is_generating = True
        self._last_review_result = None
        self._last_manual_isbn_count = 0
        self._last_updated_inventory_path = None
        self._pending_preparation = None
        self._pending_review_outcome = None
        self._authoritative_books = None
        self._window.show_home()
        self._set_inputs_enabled(False)
        self._set_status("Generating labels…", level="ok")
        self._start_generation_job(job)

    def _start_generation_job(self, job: GenerationJob) -> None:
        """Start a background worker for one generation phase."""
        thread = QThread()
        worker = GenerationWorker(
            job,
            service_factory=self._generation_service_factory,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_generation_progress)
        worker.prepared.connect(self._on_generation_prepared)
        worker.completed.connect(self._on_generation_completed)
        worker.failed.connect(self._on_generation_failed)
        worker.prepared.connect(thread.quit)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)

        def _cleanup_phase() -> None:
            if self._active_thread is thread:
                self._active_thread = None
                self._active_worker = None
            worker.deleteLater()
            thread.deleteLater()

        thread.finished.connect(_cleanup_phase)

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
    def _on_generation_prepared(self, prepared: object) -> None:
        """After import/enrichment: review if needed, then produce labels."""
        assert isinstance(prepared, PreparedGeneration)
        if not self._is_generating:
            return
        self._pending_preparation = prepared
        self._set_status("Reviewing ISBN matches…", level="ok")

        books = prepared.books
        outcome: ReviewWizardOutcome | None = None
        session = review_session_from_enrichment(prepared.enrichment)
        if session is not None:
            outcome = self._review_wizard_runner(
                session,
                self._save_updated_inventory_on_review,
            )
            if outcome is None:
                self._logger.info("ISBN review wizard dismissed without Finish")
            else:
                self._last_review_result = outcome.review_result
                self._last_manual_isbn_count = outcome.session.manual_decision_count()
                self._save_updated_inventory_on_review = (
                    outcome.save_updated_inventory
                )
                self._persist_preferences()
                self._logger.info(
                    "ISBN review finished: resolved=%s skipped=%s unresolved=%s "
                    "manual=%s save_inventory=%s",
                    outcome.review_result.resolved_count,
                    outcome.review_result.skipped_count,
                    outcome.review_result.unresolved_count,
                    self._last_manual_isbn_count,
                    outcome.save_updated_inventory,
                )
                books = books_with_review_applied(
                    prepared.books,
                    outcome.session,
                    outcome.review_result,
                )

        self._pending_review_outcome = outcome
        self._authoritative_books = tuple(books)
        review_session = outcome.session if outcome is not None else None
        produce_books = books_eligible_for_produce(
            self._authoritative_books,
            review_session,
        )
        produce_rows = source_rows_for_books(
            self._authoritative_books,
            prepared.source_rows,
            produce_books,
        )
        inventory = self._state.inventory_workbook
        output = self._state.output_workbook
        assert inventory is not None
        assert output is not None
        try:
            settings = self.build_application_settings()
        except ApplicationError as exc:
            self._is_generating = False
            self._set_status(exc.message, level="error")
            self._set_inputs_enabled(True)
            return

        self._set_status("Generating labels…", level="ok")
        self._logger.info(
            "Produce eligible books: %s of %s authoritative",
            len(produce_books),
            len(self._authoritative_books),
        )
        produce_job = GenerationJob(
            settings=settings,
            workbook_path=inventory,
            output_path=output,
            phase=GenerationPhase.PRODUCE,
            books=produce_books,
            source_rows=produce_rows,
            enrichment=prepared.enrichment,
            prior_warnings=prepared.warnings,
            books_imported=prepared.books_imported,
            started_at=prepared.started_at,
        )
        self._start_generation_job(produce_job)

    @Slot(object)
    def _on_generation_completed(self, result: object) -> None:
        assert isinstance(result, WorkbookGenerationResult)
        self._is_generating = False
        self._logger.info(
            "Generation complete: %s",
            result.to_dict()["summary"],
        )
        if self._pending_preparation is not None:
            inventory_path = self._finalize_inventory_after_generation(result)
        else:
            # Legacy full-generate stubs (no prepare/produce).
            inventory_path = self._run_interactive_review_if_needed(result)
        self._pending_preparation = None
        self._pending_review_outcome = None
        self._authoritative_books = None
        self._show_ready_to_print(result, inventory_path)

    def _finalize_inventory_after_generation(
        self,
        result: WorkbookGenerationResult,
    ) -> Path | None:
        """Write updated inventory from the post-review authoritative books."""
        self._last_updated_inventory_path = None
        outcome = self._pending_review_outcome
        if outcome is None or not outcome.save_updated_inventory:
            return None
        return self._write_updated_inventory(result, outcome)

    def _show_ready_to_print(
        self,
        result: WorkbookGenerationResult,
        inventory_path: Path | None,
    ) -> None:
        """Replace the home form with the Ready to Print completion page."""
        skipped = 0
        if self._last_review_result is not None:
            skipped = self._last_review_result.skipped_count
        summary = build_gui_completion_summary(
            result,
            updated_inventory_path=inventory_path,
            isbns_entered_manually=self._last_manual_isbn_count,
            labels_intentionally_skipped=skipped,
        )
        self._window.completion_view.populate(summary)
        self._window.show_completion()
        self._set_status("", level="ok")
        self._set_inputs_enabled(True)

    def on_completion_done(self) -> None:
        """Return to Home, clearing completion/progress while keeping settings."""
        self._window.completion_view.clear()
        self._window.show_home()
        self._last_updated_inventory_path = None
        self._refresh_ui()

    def on_open_label_workbook(self) -> None:
        """Open the generated label workbook with the OS default app."""
        summary = self._window.completion_view.summary()
        if summary is None or summary.label_workbook_path is None:
            return
        self._open_path(summary.label_workbook_path)

    def on_open_updated_inventory(self) -> None:
        """Open the updated inventory workbook when one was written."""
        summary = self._window.completion_view.summary()
        if summary is None or summary.updated_inventory_path is None:
            return
        self._open_path(summary.updated_inventory_path)

    @staticmethod
    def _default_open_path(path: Path) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def _run_interactive_review_if_needed(
        self,
        result: WorkbookGenerationResult,
    ) -> Path | None:
        """Present the review wizard when enrichment left items for teachers.

        Returns:
            Path to an updated inventory workbook when one was written;
            otherwise ``None``.
        """
        self._last_updated_inventory_path = None
        session = review_session_from_generation_result(result)
        if session is None:
            return None
        outcome = self._review_wizard_runner(
            session,
            self._save_updated_inventory_on_review,
        )
        if outcome is None:
            self._logger.info("ISBN review wizard dismissed without Finish")
            return None
        self._last_review_result = outcome.review_result
        self._last_manual_isbn_count = outcome.session.manual_decision_count()
        self._save_updated_inventory_on_review = outcome.save_updated_inventory
        self._persist_preferences()
        self._logger.info(
            "ISBN review finished: resolved=%s skipped=%s unresolved=%s "
            "manual=%s save_inventory=%s",
            outcome.review_result.resolved_count,
            outcome.review_result.skipped_count,
            outcome.review_result.unresolved_count,
            self._last_manual_isbn_count,
            outcome.save_updated_inventory,
        )
        if not outcome.save_updated_inventory:
            return None
        return self._write_updated_inventory(result, outcome)

    def _write_updated_inventory(
        self,
        result: WorkbookGenerationResult,
        outcome: ReviewWizardOutcome,
    ) -> Path | None:
        """Write a non-destructive inventory copy with accepted ISBN updates."""
        source = self._state.inventory_workbook
        if source is None:
            self._logger.warning(
                "Cannot write updated inventory: no inventory workbook selected"
            )
            return None
        books = self._authoritative_books
        source_rows: tuple[int, ...] | None = None
        if self._pending_preparation is not None:
            source_rows = self._pending_preparation.source_rows
        if books is None:
            books = result.books
        if source_rows is None:
            source_rows = result.source_rows
        if not books or not source_rows:
            self._logger.warning(
                "Cannot write updated inventory: generation result has no "
                "book/source_row data"
            )
            return None
        try:
            settings = self.build_application_settings()
            written = self._inventory_update_service.write_updated_inventory(
                source_path=source,
                settings=settings,
                books=books,
                source_rows=source_rows,
                session=outcome.session,
                review_result=outcome.review_result,
            )
        except Exception as exc:
            self._logger.error(
                "Failed to write updated inventory workbook: %s",
                exc,
                exc_info=True,
            )
            return None
        self._last_updated_inventory_path = written
        return written

    def _default_run_review_wizard(
        self,
        session: ReviewSession,
        save_updated_inventory: bool,
    ) -> ReviewWizardOutcome | None:
        dialog = ReviewWizardDialog(
            session,
            save_updated_inventory=save_updated_inventory,
            parent=self._window,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        # Finish already sealed the session inside the dialog.
        review_result = self._book_review_service.apply(dialog.session())
        return ReviewWizardOutcome(
            session=dialog.session(),
            save_updated_inventory=dialog.save_updated_inventory(),
            review_result=review_result,
        )

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
        self._pending_preparation = None
        self._pending_review_outcome = None
        self._authoritative_books = None

    def _set_inputs_enabled(self, enabled: bool) -> None:
        window = self._window
        window.inventory_browse_button.setEnabled(enabled)
        window.barcode_browse_button.setEnabled(enabled)
        window.output_browse_button.setEnabled(enabled)
        window.filename_edit.setEnabled(enabled)
        window.label_template_combo.setEnabled(enabled)
        window.show_title_checkbox.setEnabled(enabled)
        window.show_author_checkbox.setEnabled(enabled)
        window.show_barcode_checkbox.setEnabled(enabled)
        window.lookup_missing_isbns_checkbox.setEnabled(enabled)
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
        window.filename_edit.editingFinished.connect(self.on_filename_editing_finished)
        window.label_template_combo.currentIndexChanged.connect(self.on_template_changed)
        window.show_title_checkbox.toggled.connect(self.on_label_content_changed)
        window.show_author_checkbox.toggled.connect(self.on_label_content_changed)
        window.show_barcode_checkbox.toggled.connect(self.on_label_content_changed)
        window.lookup_missing_isbns_checkbox.toggled.connect(
            self.on_lookup_missing_isbns_changed
        )
        window.generate_button.clicked.connect(self.on_generate_labels)
        completion = window.completion_view
        completion.open_label_workbook_requested.connect(self.on_open_label_workbook)
        completion.open_updated_inventory_requested.connect(
            self.on_open_updated_inventory
        )
        completion.done_requested.connect(self.on_completion_done)

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
            self._state.label_folder,
            empty="No folder selected",
        )
        self._sync_filename_edit()
        self._sync_template_combo()
        self._sync_content_checkboxes()
        self._sync_lookup_missing_isbns_checkbox()

        if self._is_generating:
            self._set_inputs_enabled(False)
            return

        messages = self._state.validation_messages()
        self._set_inputs_enabled(True)
        if messages:
            self._set_status(messages[0], level="error")
        else:
            self._set_status("Ready to generate labels.", level="ok")

    def _sync_filename_edit(self) -> None:
        edit = self._window.filename_edit
        desired = self._state.label_filename or DEFAULT_LABEL_FILENAME
        if edit.text() != desired:
            edit.blockSignals(True)
            edit.setText(desired)
            edit.blockSignals(False)
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

    def _sync_lookup_missing_isbns_checkbox(self) -> None:
        checkbox = self._window.lookup_missing_isbns_checkbox
        checked = self._state.lookup_missing_isbns
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
        """Seed Files paths and review prefs from disk."""
        preferences = load_gui_preferences(path=self._preferences_file())
        inventory = usable_inventory_workbook(preferences.inventory_workbook)
        barcode = usable_barcode_folder(preferences.barcode_folder)
        label_folder = usable_label_folder(preferences.label_folder)
        if label_folder is None and preferences.output_workbook is not None:
            legacy = usable_output_workbook(preferences.output_workbook)
            if legacy is not None:
                label_folder = legacy.parent
        filename = default_label_filename(
            last_label_filename=preferences.label_filename,
            last_output_workbook=preferences.output_workbook,
        )
        if inventory is not None:
            self._state = self._state.with_inventory_workbook(inventory)
        if barcode is not None:
            self._state = self._state.with_barcode_folder(barcode)
        if label_folder is not None:
            self._state = self._state.with_label_folder(label_folder)
        self._state = self._state.with_label_filename(filename)
        self._save_updated_inventory_on_review = (
            preferences.save_updated_inventory_on_review
        )

    def _persist_preferences(self) -> None:
        """Write current Files paths and review prefs for next launch."""
        try:
            save_gui_preferences(
                GuiPreferences(
                    inventory_workbook=self._state.inventory_workbook,
                    barcode_folder=self._state.barcode_folder,
                    label_folder=self._state.label_folder,
                    label_filename=self._state.label_filename,
                    save_updated_inventory_on_review=(
                        self._save_updated_inventory_on_review
                    ),
                ),
                path=self._preferences_file(),
            )
        except OSError as exc:
            self._logger.warning("Could not save path preferences: %s", exc)

    def _default_open_inventory(self) -> Path | None:
        path, _filter = QFileDialog.getOpenFileName(
            self._window,
            "Choose Inventory Workbook",
            inventory_dialog_start_directory(
                last_inventory_workbook=self._state.inventory_workbook,
            ),
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

    def _default_open_label_folder(self) -> Path | None:
        path = QFileDialog.getExistingDirectory(
            self._window,
            "Choose Label Folder",
            label_folder_dialog_start_directory(
                last_label_folder=self._state.label_folder,
                last_output_workbook=self._state.output_workbook,
            ),
        )
        return Path(path) if path else None


def normalize_label_filename(filename: str) -> str:
    """Return a basename with a supported Excel suffix when possible."""
    cleaned = filename.strip()
    if not cleaned:
        return ""
    cleaned = Path(cleaned).name
    return ensure_excel_workbook_suffix(Path(cleaned)).name


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
