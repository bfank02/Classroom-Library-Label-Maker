"""Workbook generation service — end-to-end label workbook creation.

Coordinates import, optional ISBN enrichment, batch barcode processing, label
layout, and workbook save. Depends on :class:`WorkbookWriter` only for Excel
output (never imports openpyxl). Does not print or display UI.

Depends on :class:`BookEnrichmentService` for optional missing-ISBN lookup —
never on catalog-specific providers.
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
    BookEnrichmentResult,
    BookEnrichmentStatus,
    BookProcessingResult,
    BookProcessingStatus,
    EnrichmentSummary,
    ImportWarning,
    LabelLayoutWarning,
    WorkbookGenerationResult,
    WorkbookGenerationWarning,
)
from classroom_library_label_maker.progress import (
    GenerationProgress,
    GenerationProgressReporter,
    GenerationStage,
)
from classroom_library_label_maker.services.batch_processing_service import (
    BatchProcessingService,
)
from classroom_library_label_maker.services.book_enrichment_service import (
    BookEnrichmentService,
    book_needs_isbn_lookup,
    create_default_enrichment_service,
)
from classroom_library_label_maker.services.excel_import_service import (
    ExcelImportService,
)
from classroom_library_label_maker.services.isbn_validator import IsbnValidator
from classroom_library_label_maker.services.label_layout_service import (
    LabelLayoutService,
)
from classroom_library_label_maker.workbooks.in_memory_label_sheet_target import (
    InMemoryLabelSheetTarget,
)
from classroom_library_label_maker.workbooks.openpyxl_workbook_writer import (
    OpenPyxlWorkbookWriter,
)
from classroom_library_label_maker.workbooks.pdf_label_renderer import write_labels_pdf
from classroom_library_label_maker.workbooks.tee_label_sheet_target import (
    TeeLabelSheetTarget,
)
from classroom_library_label_maker.workbooks.workbook_writer import WorkbookWriter

_logger = get_logger("workbook_generation_service")

_DEFAULT_OUTPUT_NAME = "library_labels.xlsx"


class WorkbookGenerationService:
    """Generate a saved label workbook from an inventory spreadsheet.

    Canonical orchestration::

        ExcelImportService
            → (optional) BookEnrichmentService
            → BatchProcessingService
            → LabelLayoutService
            → WorkbookWriter.save
    """

    def __init__(
        self,
        settings: ApplicationSettings,
        *,
        importer: ExcelImportService | None = None,
        enrichment: BookEnrichmentService | None = None,
        batch_processor: BatchProcessingService | None = None,
        layout_service: LabelLayoutService | None = None,
        writer: WorkbookWriter | None = None,
        progress_reporter: GenerationProgressReporter | None = None,
    ) -> None:
        """Initialize the generation service.

        Args:
            settings: Application settings (workbook path, barcode dirs, template).
            importer: Optional import service override.
            enrichment: Optional enrichment service. When omitted and
                ``settings.lookup_missing_isbns`` is True, a default service is
                created. When lookup is disabled, enrichment is skipped.
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
        self._isbn_validator = IsbnValidator()

        if enrichment is not None:
            self._enrichment: BookEnrichmentService | None = enrichment
        elif settings.lookup_missing_isbns:
            self._enrichment = create_default_enrichment_service()
        else:
            self._enrichment = None

    def generate(
        self,
        *,
        workbook_path: Path | None = None,
        output_path: Path | None = None,
        progress_reporter: GenerationProgressReporter | None = None,
    ) -> WorkbookGenerationResult:
        """Import books, optionally enrich ISBNs, generate barcodes, layout, save.

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
        enrichment_summary = EnrichmentSummary(enabled=False)

        _logger.info(
            "Workbook generation started: inventory=%s output=%s "
            "lookup_missing_isbns=%s",
            workbook_path or self._settings.workbook_path,
            destination,
            self._settings.lookup_missing_isbns,
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

            books_for_batch = list(imported.books)
            if self._settings.lookup_missing_isbns and self._enrichment is not None:
                self._report(reporter, GenerationStage.ENRICHING)
                books_for_batch, enrichment_summary, enrich_warnings = (
                    self._enrich_missing_isbns(books_for_batch, self._enrichment)
                )
                warnings.extend(enrich_warnings)
                _logger.info(
                    "ISBN enrichment complete: looked_up=%s found=%s "
                    "ambiguous=%s not_found=%s errors=%s cache_hits=%s",
                    enrichment_summary.books_looked_up,
                    enrichment_summary.isbns_found,
                    enrichment_summary.ambiguous_matches,
                    enrichment_summary.not_found,
                    enrichment_summary.lookup_errors,
                    enrichment_summary.cache_hits,
                )

            self._report(reporter, GenerationStage.VALIDATING)
            self._report(reporter, GenerationStage.GENERATING_BARCODES)
            batch = self._batch.process_books(books_for_batch)
            _logger.info(
                "Barcode generation complete: processed=%s generated=%s reused=%s",
                batch.total_processed,
                batch.successful_generations,
                batch.existing_barcodes_skipped,
            )
            warnings.extend(self._from_batch_results(batch.results))

            barcode_paths = self._barcode_paths(batch.results)
            books_for_layout = list(books_for_batch)

            self._writer.create_workbook()
            memory_target = InMemoryLabelSheetTarget()
            try:
                self._report(reporter, GenerationStage.CREATING_LABELS)
                layout = self._layout.layout_books(
                    books_for_layout,
                    TeeLabelSheetTarget(
                        self._writer.get_label_sheet_target(),
                        memory_target,
                    ),
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

                pdf_saved: Path | None = None
                if memory_target.placements:
                    pdf_path = Path(saved).with_suffix(".pdf")
                    try:
                        template = next(iter(memory_target.templates_by_page.values()))
                        pdf_saved = write_labels_pdf(
                            memory_target.placements,
                            template,
                            pdf_path,
                        )
                        _logger.info("Print-ready PDF saved: %s", pdf_saved)
                    except Exception as exc:
                        _logger.exception("Failed writing print-ready PDF")
                        raise FileSystemError(
                            f"Failed to save print-ready PDF to {pdf_path}: {exc}",
                            cause=exc,
                        ) from exc
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
            pdf_output_path=Path(pdf_saved) if pdf_saved is not None else None,
            elapsed_seconds=elapsed,
            warnings=tuple(warnings),
            enrichment=enrichment_summary,
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

    def _enrich_missing_isbns(
        self,
        books: list[Book],
        enrichment: BookEnrichmentService,
    ) -> tuple[list[Book], EnrichmentSummary, list[WorkbookGenerationWarning]]:
        """Look up missing ISBNs; never abort the generation run."""
        hits_before = enrichment.cache_hits
        misses_before = enrichment.cache_misses

        books_with_isbn = 0
        looked_up = 0
        found = 0
        ambiguous = 0
        not_found = 0
        errors = 0
        warnings: list[WorkbookGenerationWarning] = []
        updated: list[Book] = []

        for book in books:
            if not book_needs_isbn_lookup(book):
                books_with_isbn += 1
                updated.append(book)
                continue

            looked_up += 1
            result = enrichment.enrich(book)
            next_book, warning = self._apply_enrichment_result(book, result)
            updated.append(next_book)
            if warning is not None:
                warnings.append(warning)

            if result.status is BookEnrichmentStatus.FOUND:
                if next_book.isbn != book.isbn and self._isbn_validator.is_valid(
                    next_book.isbn
                ):
                    found += 1
                else:
                    # FOUND without a usable ISBN - count as not found.
                    not_found += 1
            elif result.status is BookEnrichmentStatus.AMBIGUOUS:
                ambiguous += 1
            elif result.status is BookEnrichmentStatus.ERROR:
                errors += 1
            elif result.status in {
                BookEnrichmentStatus.NOT_FOUND,
                BookEnrichmentStatus.SKIPPED,
            }:
                not_found += 1

        summary = EnrichmentSummary(
            enabled=True,
            books_with_isbn=books_with_isbn,
            books_looked_up=looked_up,
            isbns_found=found,
            ambiguous_matches=ambiguous,
            not_found=not_found,
            lookup_errors=errors,
            cache_hits=enrichment.cache_hits - hits_before,
            cache_misses=enrichment.cache_misses - misses_before,
        )
        return updated, summary, warnings

    def _apply_enrichment_result(
        self,
        book: Book,
        result: BookEnrichmentResult,
    ) -> tuple[Book, WorkbookGenerationWarning | None]:
        """Apply a successful lookup; emit warnings for non-fatal outcomes."""
        if result.status is BookEnrichmentStatus.FOUND:
            candidate = (result.isbn or "").strip()
            if candidate and self._isbn_validator.is_valid(candidate):
                enriched = Book(
                    isbn=candidate,
                    title=book.title,
                    author=book.author,
                    copies=book.copies,
                    genre=book.genre,
                    reading_level=book.reading_level,
                    location=book.location,
                    condition=book.condition,
                )
                return enriched, None
            return book, WorkbookGenerationWarning(
                message=(
                    f"Enrichment found no usable ISBN for "
                    f"{book.title!r} by {book.author!r}"
                ),
                code="enrichment_not_found",
                isbn=book.isbn,
            )

        if result.status is BookEnrichmentStatus.AMBIGUOUS:
            return book, WorkbookGenerationWarning(
                message=(
                    f"Ambiguous ISBN match for {book.title!r} by {book.author!r}"
                    + (f": {result.message}" if result.message else "")
                ),
                code="enrichment_ambiguous",
                isbn=book.isbn,
            )

        if result.status is BookEnrichmentStatus.ERROR:
            return book, WorkbookGenerationWarning(
                message=(
                    f"ISBN lookup error for {book.title!r} by {book.author!r}"
                    + (f": {result.message}" if result.message else "")
                ),
                code="enrichment_error",
                isbn=book.isbn,
            )

        if result.status is BookEnrichmentStatus.NOT_FOUND:
            return book, WorkbookGenerationWarning(
                message=(
                    f"No ISBN found for {book.title!r} by {book.author!r}"
                ),
                code="enrichment_not_found",
                isbn=book.isbn,
            )

        return book, None

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
                        message=item.message
                        or f"ISBN validation failed for {item.isbn}",
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
