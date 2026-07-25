"""Batch orchestration for barcode generation from JSON input."""

from __future__ import annotations

from pathlib import Path

from classroom_library_label_maker.config import ExtensibilityHooks
from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.models import (
    ApplicationSettings,
    BarcodeGenerationResult,
    BarcodeStatus,
    BatchResults,
    Book,
)
from classroom_library_label_maker.services.barcode_generator import BarcodeGenerator
from classroom_library_label_maker.services.isbn_validator import IsbnValidator
from classroom_library_label_maker.services.protocols import (
    CoverDownloadService,
    IsbnLookupService,
)
from classroom_library_label_maker.utils.file_utils import write_json

_logger = get_logger("batch_processor")


class BatchProcessor:
    """Load books from JSON, validate ISBNs, and generate barcode images.

    Coordinates :class:`IsbnValidator` and :class:`BarcodeGenerator`. Optional
    lookup/cover services can be injected later without changing the core flow.
    """

    def __init__(
        self,
        settings: ApplicationSettings,
        *,
        validator: IsbnValidator | None = None,
        generator: BarcodeGenerator | None = None,
        hooks: ExtensibilityHooks | None = None,
        isbn_lookup: IsbnLookupService | None = None,
        cover_download: CoverDownloadService | None = None,
    ) -> None:
        """Initialize the batch processor.

        Args:
            settings: Application settings (paths, overwrite, version).
            validator: Optional ISBN validator override.
            generator: Optional barcode generator override.
            hooks: Feature flags for future extensions.
            isbn_lookup: Optional ISBN lookup service (future).
            cover_download: Optional cover download service (future).
        """
        self._settings = settings
        self._validator = validator or IsbnValidator()
        self._generator = generator or BarcodeGenerator()
        self._hooks = hooks or ExtensibilityHooks()
        self._isbn_lookup = isbn_lookup
        self._cover_download = cover_download

    def run(self) -> BatchResults:
        """Execute the full batch pipeline and write results JSON.

        Returns:
            Aggregate :class:`BatchResults` for the run.

        Raises:
            ValueError: If required run paths are missing from settings.
        """
        if self._settings.input_path is None:
            raise ValueError("settings.input_path is required for a batch run")
        if self._settings.results_path is None:
            raise ValueError("settings.results_path is required for a batch run")

        _logger.info("Starting batch from %s", self._settings.input_path)
        books = self.load_books(self._settings.input_path)
        results = self.process_books(books)
        batch = BatchResults(
            results=results,
            input_path=self._settings.input_path,
            output_dir=self._settings.barcode_output_directory,
        )
        self.write_results(batch, self._settings.results_path)
        _logger.info(
            "Batch complete: generated=%s skipped=%s errors=%s",
            batch.generated_count,
            batch.skipped_count,
            batch.error_count,
        )
        return batch

    def load_books(self, input_path: Path) -> list[Book]:
        """Load book records from a JSON file.

        Expected JSON shapes (either is accepted once implemented):

        * ``{\"books\": [ {...}, ... ]}``
        * ``[ {...}, ... ]``

        Args:
            input_path: Path to the input JSON file.

        Returns:
            A list of :class:`Book` instances.

        Raises:
            NotImplementedError: Until JSON loading is implemented.
        """
        # Will use utils.file_utils.read_json() and Book.from_dict() when the
        # barcode engine feature work lands.
        _ = input_path
        raise NotImplementedError("JSON book loading is not implemented")

    def process_books(self, books: list[Book]) -> list[BarcodeGenerationResult]:
        """Validate ISBNs and generate barcodes for each book.

        Args:
            books: Books loaded from the input file.

        Returns:
            Per-book :class:`BarcodeGenerationResult` values.
        """
        return [self.process_book(book) for book in books]

    def process_book(self, book: Book) -> BarcodeGenerationResult:
        """Process a single book: validate, optionally enrich, generate PNG.

        Args:
            book: Book record to process.

        Returns:
            The :class:`BarcodeGenerationResult` for this book.
        """
        validation = self._validator.validate(book.isbn)
        if not validation.is_valid:
            message = "; ".join(validation.errors) or "Invalid ISBN"
            _logger.warning("Invalid ISBN for %r: %s", book.title, message)
            return BarcodeGenerationResult(
                isbn=book.isbn,
                status=BarcodeStatus.INVALID_ISBN,
                message=message,
                title=book.title,
            )

        isbn = validation.isbn
        self._maybe_enrich(book, isbn)

        try:
            path, created = self._generator.generate_if_missing(
                isbn,
                self._settings.barcode_output_directory,
                overwrite=self._settings.overwrite,
            )
        except Exception as exc:
            _logger.exception("Failed generating barcode for %s", isbn)
            return BarcodeGenerationResult(
                isbn=isbn,
                status=BarcodeStatus.ERROR,
                message=str(exc),
                title=book.title,
            )

        if created:
            return BarcodeGenerationResult(
                isbn=isbn,
                status=BarcodeStatus.GENERATED,
                output_path=path,
                message="Barcode image created",
                title=book.title,
            )

        return BarcodeGenerationResult(
            isbn=isbn,
            status=BarcodeStatus.ALREADY_EXISTS,
            output_path=path,
            message="Barcode image already exists",
            title=book.title,
        )

    def write_results(self, batch: BatchResults, results_path: Path) -> None:
        """Write batch results to a JSON file.

        Args:
            batch: Aggregate results to serialize.
            results_path: Destination path for the results JSON.
        """
        # Final results schema will be confirmed with Excel / VBA consumers
        # during the Excel integration sprint.
        write_json(results_path, batch.to_dict())
        _logger.info("Wrote results to %s", results_path)

    def _maybe_enrich(self, book: Book, isbn: str) -> None:
        """Apply optional future enrichment hooks (lookup / covers).

        Args:
            book: Book being processed.
            isbn: Normalized ISBN.
        """
        if self._hooks.enable_isbn_lookup and self._isbn_lookup is not None:
            # Merge lookup fields into Book when providers are implemented.
            _logger.debug("ISBN lookup enabled but not implemented for %s", isbn)
            _ = book

        if self._hooks.enable_cover_download and self._cover_download is not None:
            # Persist cover paths when providers are implemented.
            _logger.debug("Cover download enabled but not implemented for %s", isbn)
            _ = book
