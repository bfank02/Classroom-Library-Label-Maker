"""Barcode generation service — create EAN-13 PNG images for books.

This service is the reusable engine for barcode image creation. It assumes
ISBNs on :class:`~classroom_library_label_maker.models.Book` instances are
already validated and does not re-run ISBN validation.

Rendering is delegated to a :class:`BarcodeRenderer` implementation; this
module never imports third-party barcode libraries.
"""

from __future__ import annotations

from pathlib import Path

from classroom_library_label_maker.constants import DEFAULT_BARCODE_EXTENSION
from classroom_library_label_maker.exceptions import (
    BarcodeGenerationError,
    FileSystemError,
)
from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.models import (
    ApplicationSettings,
    BarcodeGenerationResult,
    BarcodeStatus,
    Book,
)
from classroom_library_label_maker.rendering.barcode_renderer import (
    PythonBarcodeRenderer,
)
from classroom_library_label_maker.rendering.renderer import (
    BarcodeRenderer,
    BarcodeSymbology,
)
from classroom_library_label_maker.services.isbn_validator import IsbnValidator
from classroom_library_label_maker.utils.file_utils import (
    ensure_directory,
    file_exists,
)

_logger = get_logger("barcode_generation_service")


class BarcodeGenerationService:
    """Generate EAN-13 barcode PNG files for validated books.

    Responsibilities are limited to:

    * Resolving output paths from :class:`ApplicationSettings`
    * Skipping existing files (``ALREADY_EXISTS``)
    * Delegating image encoding to a :class:`BarcodeRenderer`
    * Logging and mapping unexpected failures to the application exception hierarchy
    """

    def __init__(
        self,
        settings: ApplicationSettings,
        *,
        renderer: BarcodeRenderer | None = None,
        filename_extension: str = DEFAULT_BARCODE_EXTENSION,
    ) -> None:
        """Initialize the service.

        Args:
            settings: Application settings (uses ``barcode_output_directory``).
            renderer: Optional renderer override (defaults to
                :class:`PythonBarcodeRenderer`).
            filename_extension: Image file extension including the leading dot.
        """
        self._settings = settings
        self._renderer: BarcodeRenderer = (
            renderer or PythonBarcodeRenderer.from_settings(settings)
        )
        self._extension = filename_extension
        self._normalizer = IsbnValidator()

    def generate_for_book(self, book: Book) -> BarcodeGenerationResult:
        """Generate a barcode PNG for a single validated book.

        Args:
            book: Book whose ISBN is assumed already validated.

        Returns:
            A :class:`BarcodeGenerationResult` with ``GENERATED`` or
            ``ALREADY_EXISTS``.

        Raises:
            FileSystemError: When directories or files cannot be created/written.
            BarcodeGenerationError: When rendering fails unexpectedly.
        """
        isbn = self._normalized_isbn(book)
        output_path = self.output_path_for(isbn)

        if file_exists(output_path):
            _logger.info("Skipped existing barcode file: %s", output_path)
            return BarcodeGenerationResult(
                isbn=isbn,
                status=BarcodeStatus.ALREADY_EXISTS,
                output_path=output_path,
                message="Barcode image already exists",
                title=book.title,
            )

        self._ensure_output_directory()

        _logger.info("Barcode generation started: isbn=%s path=%s", isbn, output_path)
        try:
            written = self._renderer.render_to_file(
                isbn,
                output_path,
                symbology=BarcodeSymbology.EAN13,
            )
        except OSError as exc:
            _logger.error(
                "Filesystem failure during barcode generation for %s: %s",
                isbn,
                exc,
            )
            raise FileSystemError(
                f"Failed to write barcode image for ISBN {isbn}",
                cause=exc,
            ) from exc
        except Exception as exc:
            _logger.error(
                "Rendering failure during barcode generation for %s: %s",
                isbn,
                exc,
            )
            raise BarcodeGenerationError(
                f"Failed to render barcode for ISBN {isbn}",
                cause=exc,
            ) from exc

        _logger.info(
            "Barcode generation completed: isbn=%s path=%s",
            isbn,
            written,
        )
        return BarcodeGenerationResult(
            isbn=isbn,
            status=BarcodeStatus.GENERATED,
            output_path=Path(written),
            message="Barcode image created",
            title=book.title,
        )

    def output_path_for(self, isbn: str) -> Path:
        """Return the PNG path for a normalized ISBN under configured output.

        Args:
            isbn: Normalized ISBN digits (filename stem).

        Returns:
            Absolute or relative path ``{barcode_output_directory}/{isbn}.png``.
        """
        directory = Path(self._settings.barcode_output_directory)
        return directory / f"{isbn}{self._extension}"

    def _normalized_isbn(self, book: Book) -> str:
        """Return ISBN digits for filenames without re-validating.

        Normalization only strips formatting so ``<ISBN>.png`` names are stable.
        Callers must validate ISBNs before invoking this service.
        """
        return self._normalizer.normalize(book.isbn)

    def _ensure_output_directory(self) -> None:
        """Create the configured barcode output directory if missing."""
        directory = Path(self._settings.barcode_output_directory)
        try:
            ensure_directory(directory)
        except OSError as exc:
            _logger.error(
                "Filesystem failure creating output directory %s: %s",
                directory,
                exc,
            )
            raise FileSystemError(
                f"Failed to create barcode output directory: {directory}",
                cause=exc,
            ) from exc
