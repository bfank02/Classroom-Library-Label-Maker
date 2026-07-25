"""Workbook generation service — end-to-end label workbook creation.

Coordinates import, batch barcode processing, label layout, and workbook
save. Depends on :class:`WorkbookWriter` only for Excel output (never imports
openpyxl). Does not print or display UI.
"""

from __future__ import annotations

from pathlib import Path
import time

from classroom_library_label_maker.exceptions import (
    ApplicationError,
    ConfigurationError,
    FileSystemError,
    InvalidWorkbookError,
    LabelLayoutError,
    WorkbookGenerationError,
)
from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.models import (
    ApplicationSettings,
    Book,
    BookProcessingResult,
    BookProcessingStatus,
    ImportWarning,
    LabelLayoutWarning,
    WorkbookGenerationResult,
    WorkbookGenerationWarning,
)
from classroom_library_label_maker.services.batch_processing_service import (
    BatchProcessingService,
)
from classroom_library_label_maker.services.excel_import_service import (
    ExcelImportService,
)
from classroom_library_label_maker.services.label_layout_service import (
    LabelLayoutService,
)
from classroom_library_label_maker.workbooks.openpyxl_workbook_writer import (
    OpenPyxlWorkbookWriter,
)
from classroom_library_label_maker.workbooks.workbook_writer import WorkbookWriter
from classroom_library_label_maker.progress import (
    GenerationProgress,
    GenerationProgressReporter,
    GenerationStage,
)

_logger = get_logger("workbook_generation_service")

_DEFAULT_OUTPUT_NAME = "library_labels.xlsx"


class WorkbookGenerationService:
    """Generate a saved label workbook from an inventory spreadsheet.

    Canonical orchestration::

        ExcelImportService → BatchProcessingService → LabelLayoutService
        (via WorkbookWriter LabelSheetTarget) → WorkbookWriter.save
    """

    def __init__(
        self,
        settings: ApplicationSettings,
        *,
        importer: ExcelImportService | None = None,
        batch_processor: BatchProcessingService | None = None,
        layout_service: LabelLayoutService | None = None,
        writer: WorkbookWriter | None = None,
        progress_reporter: GenerationProgressReporter | None = None,
    ) -> None:
        """Initialize the generation service.

        Args:
            settings: Application settings (workbook path, barcode dirs, template).
            importer: Optional import service override.
            batch_processor: Optional batch processing override.
            layout_service: Optional layout service override.
            writer: Optional workbook writer (defaults to
                :class:`OpenPyxlWorkbookWriter`).
            progress_reporter: Optional progress hook (GUI/CLI); Qt-unaware.
        """
        self._settings = settings
        self._importer = importer or ExcelImportService(settings)
        self._batch = batch_processor or BatchProcessingService(settings)
        self._layout = layout_service or LabelLayoutService(settings)
        self._writer: WorkbookWriter = writer or OpenPyxlWorkbookWriter()
        self._progress = progress_reporter

    def generate(
        self,
        *,
        workbook_path: Path | None = None,
        output_path: Path | None = None,
        progress_reporter: GenerationProgressReporter | None = None,
    ) -> WorkbookGenerationResult:
        """Import books, generate barcodes, layout labels, and save a workbook.

        Args:
            workbook_path: Optional inventory workbook override.
            output_path: Optional destination for the label workbook. Defaults to
                ``{project_root}/output/library_labels.xlsx``.
            progress_reporter: Optional per-call progress override. When omitted,
                uses the reporter supplied at construction (if any).

        Returns:
            Immutable :class:`WorkbookGenerationResult`.

        Raises:
            ConfigurationError: When required paths/settings are missing.
            FileSystemError: When files cannot be read or written.
            InvalidWorkbookError: When the inventory workbook is invalid.
            LabelLayoutError: When layout fails unrecoverably.
            WorkbookGenerationError: When orchestration fails unrecoverably.
        """
        reporter = (
            progress_reporter if progress_reporter is not None else self._progress
        )
        started = time.perf_counter()
        destination = self._resolve_output_path(output_path)
        warnings: list[WorkbookGenerationWarning] = []

        _logger.info(
            "Workbook generation started: inventory=%s output=%s",
            workbook_path or self._settings.workbook_path,
            destination,
        )

        try:
            self._report(reporter, GenerationStage.IMPORTING)
            imported = self._importer.import_books(workbook_path)
            _logger.info(
                "Workbook imported: books=%s warnings=%s",
                len(imported.books),
                len(imported.warnings),
            )
            warnings.extend(self._from_import_warnings(imported.warnings))

            self._report(reporter, GenerationStage.VALIDATING)
            self._report(reporter, GenerationStage.GENERATING_BARCODES)
            batch = self._batch.process_books(imported.books)
            _logger.info(
                "Barcode generation complete: processed=%s generated=%s reused=%s",
                batch.total_processed,
                batch.successful_generations,
                batch.existing_barcodes_skipped,
            )
            warnings.extend(self._from_batch_results(batch.results))

            barcode_paths = self._barcode_paths(batch.results)
            books_for_layout = list(imported.books)

            self._writer.create_workbook()
            try:
                self._report(reporter, GenerationStage.CREATING_LABELS)
                layout = self._layout.layout_books(
                    books_for_layout,
                    self._writer.get_label_sheet_target(),
                    barcode_paths=barcode_paths,
                )
                _logger.info(
                    "Layout complete: labels=%s pages=%s warnings=%s",
                    layout.labels_placed,
                    layout.pages_created,
                    len(layout.warnings),
                )
                warnings.extend(self._from_layout_warnings(layout.warnings))

                self._report(reporter, GenerationStage.SAVING)
                try:
                    saved = self._writer.save(destination)
                except OSError as exc:
                    raise FileSystemError(
                        f"Failed to save label workbook to {destination}: {exc}",
                        cause=exc,
                    ) from exc
                _logger.info("Workbook saved: %s", saved)
            finally:
                self._writer.close()

        except (
            ConfigurationError,
            FileSystemError,
            InvalidWorkbookError,
            LabelLayoutError,
            WorkbookGenerationError,
        ):
            raise
        except ApplicationError:
            raise
        except Exception as exc:
            raise WorkbookGenerationError(
                f"Workbook generation failed: {exc}",
                cause=exc,
            ) from exc

        elapsed = time.perf_counter() - started
        result = WorkbookGenerationResult(
            books_imported=len(imported.books),
            books_processed=batch.total_processed,
            labels_created=layout.labels_placed,
            pages_created=layout.pages_created,
            barcodes_generated=batch.successful_generations,
            barcodes_reused=batch.existing_barcodes_skipped,
            output_path=Path(saved),
            elapsed_seconds=elapsed,
            warnings=tuple(warnings),
        )
        _logger.info(
            "Workbook generation complete: imported=%s labels=%s pages=%s "
            "warnings=%s elapsed=%.3fs",
            result.books_imported,
            result.labels_created,
            result.pages_created,
            len(result.warnings),
            result.elapsed_seconds,
        )
        return result

    def _report(
        self,
        reporter: GenerationProgressReporter | None,
        stage: GenerationStage,
    ) -> None:
        if reporter is None:
            return
        progress = GenerationProgress.for_stage(stage)
        try:
            reporter.on_progress(progress)
        except Exception:
            _logger.exception(
                "Progress reporter failed for stage %s",
                stage.value,
            )

    def _resolve_output_path(self, output_path: Path | None) -> Path:
        if output_path is not None:
            return Path(output_path)
        return Path(self._settings.project_root) / "output" / _DEFAULT_OUTPUT_NAME

    @staticmethod
    def _barcode_paths(
        results: list[BookProcessingResult],
    ) -> dict[str, Path]:
        paths: dict[str, Path] = {}
        for item in results:
            if item.output_path is None:
                continue
            if item.status in {
                BookProcessingStatus.GENERATED,
                BookProcessingStatus.ALREADY_EXISTS,
            }:
                paths[item.isbn] = Path(item.output_path)
        return paths

    @staticmethod
    def _from_import_warnings(
        warnings: tuple[ImportWarning, ...] | list[ImportWarning],
    ) -> list[WorkbookGenerationWarning]:
        return [
            WorkbookGenerationWarning(
                message=warning.message,
                code=warning.code or "import",
                row_number=warning.row_number,
            )
            for warning in warnings
        ]

    @staticmethod
    def _from_layout_warnings(
        warnings: tuple[LabelLayoutWarning, ...],
    ) -> list[WorkbookGenerationWarning]:
        return [
            WorkbookGenerationWarning(
                message=warning.message,
                code=warning.code or "layout",
                isbn=warning.isbn,
                page_number=warning.page_number,
            )
            for warning in warnings
        ]

    @staticmethod
    def _from_batch_results(
        results: list[BookProcessingResult],
    ) -> list[WorkbookGenerationWarning]:
        warnings: list[WorkbookGenerationWarning] = []
        for item in results:
            if item.status == BookProcessingStatus.VALIDATION_FAILED:
                warnings.append(
                    WorkbookGenerationWarning(
                        message=item.message or f"ISBN validation failed for {item.isbn}",
                        code="validation_failed",
                        isbn=item.isbn,
                    )
                )
            elif item.status == BookProcessingStatus.GENERATION_FAILED:
                warnings.append(
                    WorkbookGenerationWarning(
                        message=item.message
                        or f"Barcode generation failed for {item.isbn}",
                        code="generation_failed",
                        isbn=item.isbn,
                    )
                )
        return warnings
