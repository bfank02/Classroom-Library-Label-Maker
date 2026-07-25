"""Batch processing service — orchestrate validation and barcode generation.

This service is the reusable orchestration layer for collections of
:class:`~classroom_library_label_maker.models.Book` objects. It reuses
:class:`~classroom_library_label_maker.services.isbn_validator.IsbnValidator`
and
:class:`~classroom_library_label_maker.services.barcode_generation_service.BarcodeGenerationService`
without duplicating their logic.

Per-book failures never abort the batch. Optional progress reporting is
supported via :class:`BatchProgressReporter` so future CLI/UI layers can
observe progress without API changes.
"""

from __future__ import annotations

from collections.abc import Sequence
import time

from classroom_library_label_maker.exceptions import ApplicationError
from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.models import (
    ApplicationSettings,
    BarcodeStatus,
    BatchProcessingResult,
    Book,
    BookProcessingResult,
    BookProcessingStatus,
)
from classroom_library_label_maker.services.barcode_generation_service import (
    BarcodeGenerationService,
)
from classroom_library_label_maker.services.isbn_validator import IsbnValidator
from classroom_library_label_maker.services.protocols import BatchProgressReporter

_logger = get_logger("batch_processing_service")


class BatchProcessingService:
    """Process collections of books: validate ISBNs, then generate barcodes.

    Responsibilities:

    * Validate each book with :class:`IsbnValidator`
    * Generate barcodes for valid books with :class:`BarcodeGenerationService`
    * Continue after validation or generation failures
    * Aggregate per-book outcomes into :class:`BatchProcessingResult`
    * Optionally notify a :class:`BatchProgressReporter` after each book
    """

    def __init__(
        self,
        settings: ApplicationSettings,
        *,
        validator: IsbnValidator | None = None,
        generator: BarcodeGenerationService | None = None,
        progress_reporter: BatchProgressReporter | None = None,
    ) -> None:
        """Initialize the batch processing service.

        Args:
            settings: Application settings passed through to generation.
            validator: Optional ISBN validator override.
            generator: Optional barcode generation service override.
            progress_reporter: Optional progress hook for future UI/CLI.
        """
        self._settings = settings
        self._validator = validator or IsbnValidator()
        self._generator = generator or BarcodeGenerationService(settings)
        self._progress = progress_reporter

    def process_books(self, books: Sequence[Book]) -> BatchProcessingResult:
        """Validate and generate barcodes for every book in ``books``.

        Processing continues after individual validation or generation
        failures. The batch never raises for expected per-book errors.

        Args:
            books: Collection of books to process (may be empty).

        Returns:
            Aggregate :class:`BatchProcessingResult` including timing and
            per-book outcomes in input order.
        """
        total = len(books)
        _logger.info("Batch processing started: total=%s", total)
        self._notify_started(total)

        started = time.perf_counter()
        results: list[BookProcessingResult] = []

        for index, book in enumerate(books, start=1):
            result = self._process_one(book)
            results.append(result)
            self._notify_book_processed(index, total, result)

        elapsed = time.perf_counter() - started
        batch = BatchProcessingResult(results=results, elapsed_seconds=elapsed)

        _logger.info(
            "Batch processing completed: total=%s generated=%s skipped=%s "
            "validation_failures=%s generation_failures=%s elapsed=%.3fs",
            batch.total_processed,
            batch.successful_generations,
            batch.existing_barcodes_skipped,
            batch.validation_failures,
            batch.generation_failures,
            batch.elapsed_seconds,
        )
        self._notify_completed(total)
        return batch

    def _process_one(self, book: Book) -> BookProcessingResult:
        """Validate one book and generate a barcode when valid."""
        validation = self._validator.validate(book.isbn)
        if not validation.is_valid:
            message = "; ".join(validation.errors) or "Invalid ISBN"
            return BookProcessingResult(
                isbn=validation.isbn or book.isbn,
                title=book.title,
                status=BookProcessingStatus.VALIDATION_FAILED,
                message=message,
                validation=validation,
            )

        try:
            generation = self._generator.generate_for_book(book)
        except ApplicationError as exc:
            _logger.error(
                "Unexpected generation failure for isbn=%s title=%r: %s",
                validation.isbn,
                book.title,
                exc,
            )
            return BookProcessingResult(
                isbn=validation.isbn,
                title=book.title,
                status=BookProcessingStatus.GENERATION_FAILED,
                message=str(exc),
                validation=validation,
            )
        except Exception as exc:
            _logger.exception(
                "Unexpected generation failure for isbn=%s title=%r",
                validation.isbn,
                book.title,
            )
            return BookProcessingResult(
                isbn=validation.isbn,
                title=book.title,
                status=BookProcessingStatus.GENERATION_FAILED,
                message=str(exc),
                validation=validation,
            )

        if generation.status is BarcodeStatus.GENERATED:
            status = BookProcessingStatus.GENERATED
        elif generation.status is BarcodeStatus.ALREADY_EXISTS:
            status = BookProcessingStatus.ALREADY_EXISTS
        else:
            # Defensive: treat unexpected generator statuses as generation failure.
            status = BookProcessingStatus.GENERATION_FAILED

        return BookProcessingResult(
            isbn=generation.isbn or validation.isbn,
            title=book.title,
            status=status,
            output_path=generation.output_path,
            message=generation.message,
            validation=validation,
            generation=generation,
        )

    def _notify_started(self, total: int) -> None:
        if self._progress is None:
            return
        try:
            self._progress.on_batch_started(total)
        except Exception:
            _logger.exception("Progress reporter on_batch_started failed")

    def _notify_book_processed(
        self,
        index: int,
        total: int,
        result: BookProcessingResult,
    ) -> None:
        if self._progress is None:
            return
        try:
            self._progress.on_book_processed(index, total, result)
        except Exception:
            _logger.exception("Progress reporter on_book_processed failed")

    def _notify_completed(self, total: int) -> None:
        if self._progress is None:
            return
        try:
            self._progress.on_batch_completed(total)
        except Exception:
            _logger.exception("Progress reporter on_batch_completed failed")
