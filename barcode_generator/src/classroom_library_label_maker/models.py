"""Domain models for classroom library barcode generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from classroom_library_label_maker.constants import (
    DEFAULT_BARCODE_DPI,
    DEFAULT_BARCODE_FONT_SIZE,
    DEFAULT_BARCODE_MODULE_HEIGHT,
    DEFAULT_BARCODE_MODULE_WIDTH,
    DEFAULT_BARCODE_QUIET_ZONE,
    DEFAULT_LABEL_TEMPLATE_ID,
    DEFAULT_WORKBOOK_COLUMN_AUTHOR,
    DEFAULT_WORKBOOK_COLUMN_COPIES,
    DEFAULT_WORKBOOK_COLUMN_ISBN,
    DEFAULT_WORKBOOK_COLUMN_TITLE,
    DEFAULT_WORKBOOK_HEADER_ROW,
    DEFAULT_WORKBOOK_SHEET_NAME,
)


class BarcodeStatus(StrEnum):
    """Outcome status for a single barcode generation attempt."""

    GENERATED = "generated"
    SKIPPED = "skipped"
    ALREADY_EXISTS = "already_exists"
    INVALID_ISBN = "invalid_isbn"
    ERROR = "error"


@dataclass(slots=True)
class Book:
    """A book in the classroom library inventory.

    Attributes:
        isbn: ISBN value (ISBN-13 preferred; may include hyphens/spaces).
        title: Book title.
        author: Primary author name.
        copies: Number of physical copies in the inventory.
        genre: Optional genre / category label.
        reading_level: Optional reading level (e.g. Fountas & Pinnell, Lexile).
        location: Optional shelf / bin location.
        condition: Optional physical condition note.
    """

    isbn: str
    title: str
    author: str
    copies: int = 1
    genre: str | None = None
    reading_level: str | None = None
    location: str | None = None
    condition: str | None = None

    def __post_init__(self) -> None:
        """Validate required fields and normalize simple types."""
        if not self.isbn or not str(self.isbn).strip():
            raise ValueError("isbn is required")
        if not self.title or not str(self.title).strip():
            raise ValueError("title is required")
        if not self.author or not str(self.author).strip():
            raise ValueError("author is required")
        if int(self.copies) < 1:
            raise ValueError("copies must be >= 1")
        object.__setattr__(self, "copies", int(self.copies))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Book:
        """Create a :class:`Book` from a raw JSON object.

        Accepts ``isbn`` or legacy ``isbn13`` for transitional sample files.

        Args:
            data: Mapping with book fields.

        Returns:
            A validated :class:`Book` instance.

        Raises:
            KeyError: If a required field is missing.
            ValueError: If field values fail validation.
        """
        isbn = data.get("isbn", data.get("isbn13"))
        if isbn is None:
            raise KeyError("isbn")
        return cls(
            isbn=str(isbn),
            title=str(data["title"]),
            author=str(data["author"]),
            copies=int(data.get("copies", 1)),
            genre=_optional_str(data.get("genre")),
            reading_level=_optional_str(data.get("reading_level")),
            location=_optional_str(data.get("location")),
            condition=_optional_str(data.get("condition")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize this book to a JSON-compatible dictionary.

        Returns:
            A dictionary representation of the book.
        """
        payload: dict[str, Any] = {
            "isbn": self.isbn,
            "title": self.title,
            "author": self.author,
            "copies": self.copies,
        }
        if self.genre is not None:
            payload["genre"] = self.genre
        if self.reading_level is not None:
            payload["reading_level"] = self.reading_level
        if self.location is not None:
            payload["location"] = self.location
        if self.condition is not None:
            payload["condition"] = self.condition
        return payload

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return (
            f"Book(isbn={self.isbn!r}, title={self.title!r}, "
            f"author={self.author!r}, copies={self.copies})"
        )


class ValidationErrorCode(StrEnum):
    """Machine-readable ISBN validation failure codes.

    Each member carries a default user-facing ``message``. Prefer
    ``error_code.message`` over duplicated string literals when building
    :class:`ValidationResult` values.
    """

    def __new__(cls, value: str, message: str = "") -> ValidationErrorCode:
        """Create an enum member with a stable code value and default message."""
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj._message_ = message
        return obj

    NONE = ("none", "")
    EMPTY = ("empty", "ISBN is empty")
    NON_NUMERIC = (
        "non_numeric",
        "ISBN must contain only digits after normalization",
    )
    INVALID_LENGTH = (
        "invalid_length",
        "ISBN-13 must contain exactly 13 digits",
    )
    INVALID_PREFIX = (
        "invalid_prefix",
        "ISBN-13 prefix must be 978 or 979",
    )
    INVALID_CHECKSUM = (
        "invalid_checksum",
        "ISBN-13 check digit is invalid",
    )

    @property
    def message(self) -> str:
        """Return the default user-facing message for this error code."""
        return self._message_


@dataclass(slots=True)
class ValidationResult:
    """Outcome of validating a single ISBN value.

    Attributes:
        isbn: Normalized ISBN when available; empty string for empty/None input.
        is_valid: Whether the ISBN passed validation.
        errors: Human-readable messages (from ``error_code.message`` when
            invalid; empty when valid).
        error_code: Machine-readable failure code (``NONE`` when valid).
    """

    isbn: str
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    error_code: ValidationErrorCode = ValidationErrorCode.NONE

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return (
            f"ValidationResult(isbn={self.isbn!r}, is_valid={self.is_valid}, "
            f"error_code={self.error_code!r}, errors={self.errors!r})"
        )


@dataclass(slots=True)
class BarcodeGenerationResult:
    """Result of generating (or attempting to generate) one barcode image.

    Attributes:
        isbn: ISBN associated with this result.
        status: Generation outcome.
        output_path: Path to the PNG when generated or already present.
        message: Optional human-readable detail for logs / results JSON.
        title: Optional title echoed from the source book for reporting.
    """

    isbn: str
    status: BarcodeStatus
    output_path: Path | None = None
    message: str = ""
    title: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize this result to a JSON-compatible dictionary.

        Returns:
            A dictionary representation of the result.
        """
        return {
            "isbn": self.isbn,
            "status": self.status.value,
            "output_path": str(self.output_path) if self.output_path else None,
            "message": self.message,
            "title": self.title,
        }

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return (
            f"BarcodeGenerationResult(isbn={self.isbn!r}, "
            f"status={self.status!r}, output_path={self.output_path!r})"
        )


@dataclass(slots=True)
class BatchResults:
    """Deprecated: aggregate results for the legacy CLI :class:`~classroom_library_label_maker.services.batch_processor.BatchProcessor`.

    **Do not use for new features.** Prefer
    :class:`BatchProcessingResult` with :class:`BookProcessingResult`.

    Attributes:
        results: Per-book barcode generation outcomes.
        input_path: Source JSON path that was processed.
        output_dir: Directory used for barcode images.
    """

    results: list[BarcodeGenerationResult] = field(default_factory=list)
    input_path: Path | None = None
    output_dir: Path | None = None

    @property
    def generated_count(self) -> int:
        """Number of newly generated barcode images."""
        return sum(1 for r in self.results if r.status == BarcodeStatus.GENERATED)

    @property
    def skipped_count(self) -> int:
        """Number of barcodes skipped or already existing."""
        return sum(
            1
            for r in self.results
            if r.status in {BarcodeStatus.SKIPPED, BarcodeStatus.ALREADY_EXISTS}
        )

    @property
    def error_count(self) -> int:
        """Number of invalid ISBN or other error outcomes."""
        return sum(
            1
            for r in self.results
            if r.status in {BarcodeStatus.INVALID_ISBN, BarcodeStatus.ERROR}
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize batch results to a JSON-compatible dictionary.

        Returns:
            A dictionary suitable for writing to the results JSON file.
        """
        return {
            "summary": {
                "total": len(self.results),
                "generated": self.generated_count,
                "skipped": self.skipped_count,
                "errors": self.error_count,
            },
            "input_path": str(self.input_path) if self.input_path else None,
            "output_dir": str(self.output_dir) if self.output_dir else None,
            "results": [result.to_dict() for result in self.results],
        }

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return (
            f"BatchResults(total={len(self.results)}, "
            f"generated={self.generated_count}, skipped={self.skipped_count}, "
            f"errors={self.error_count})"
        )


class BookProcessingStatus(StrEnum):
    """Outcome status for processing a single book in a batch."""

    GENERATED = "generated"
    ALREADY_EXISTS = "already_exists"
    VALIDATION_FAILED = "validation_failed"
    GENERATION_FAILED = "generation_failed"


@dataclass(slots=True)
class BookProcessingResult:
    """Result of validating and optionally generating a barcode for one book.

    Attributes:
        isbn: Normalized ISBN when available; otherwise the original input ISBN.
        title: Book title echoed for reporting.
        status: Per-book processing outcome.
        output_path: PNG path when generated or already present.
        message: Human-readable detail for logs and summaries.
        validation: ISBN validation result when validation ran.
        generation: Barcode generation result when generation was attempted.
    """

    isbn: str
    title: str
    status: BookProcessingStatus
    output_path: Path | None = None
    message: str = ""
    validation: ValidationResult | None = None
    generation: BarcodeGenerationResult | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize this result to a JSON-compatible dictionary."""
        payload: dict[str, Any] = {
            "isbn": self.isbn,
            "title": self.title,
            "status": self.status.value,
            "output_path": str(self.output_path) if self.output_path else None,
            "message": self.message,
        }
        if self.validation is not None:
            payload["validation"] = {
                "isbn": self.validation.isbn,
                "is_valid": self.validation.is_valid,
                "error_code": self.validation.error_code.value,
                "errors": list(self.validation.errors),
            }
        if self.generation is not None:
            payload["generation"] = self.generation.to_dict()
        return payload

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return (
            f"BookProcessingResult(isbn={self.isbn!r}, "
            f"status={self.status!r}, title={self.title!r})"
        )


@dataclass(slots=True)
class BatchProcessingResult:
    """Aggregate outcome for processing a collection of books.

    Attributes:
        results: Per-book processing outcomes in input order.
        elapsed_seconds: Wall-clock duration of the batch run.
    """

    results: list[BookProcessingResult] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    @property
    def total_processed(self) -> int:
        """Number of books processed (including failures)."""
        return len(self.results)

    @property
    def successful_generations(self) -> int:
        """Number of newly generated barcode images."""
        return sum(
            1 for r in self.results if r.status == BookProcessingStatus.GENERATED
        )

    @property
    def existing_barcodes_skipped(self) -> int:
        """Number of books skipped because a barcode file already existed."""
        return sum(
            1 for r in self.results if r.status == BookProcessingStatus.ALREADY_EXISTS
        )

    @property
    def validation_failures(self) -> int:
        """Number of books that failed ISBN validation."""
        return sum(
            1
            for r in self.results
            if r.status == BookProcessingStatus.VALIDATION_FAILED
        )

    @property
    def generation_failures(self) -> int:
        """Number of books that failed during barcode generation."""
        return sum(
            1
            for r in self.results
            if r.status == BookProcessingStatus.GENERATION_FAILED
        )

    @property
    def books_per_second(self) -> float:
        """Derived throughput: ``total_processed / elapsed_seconds``.

        Returns ``0.0`` when no time has elapsed (avoids division by zero).
        """
        if self.elapsed_seconds <= 0.0:
            return 0.0
        return self.total_processed / self.elapsed_seconds

    def to_dict(self) -> dict[str, Any]:
        """Serialize batch processing results to a JSON-compatible dictionary."""
        return {
            "summary": {
                "total_processed": self.total_processed,
                "successful_generations": self.successful_generations,
                "existing_barcodes_skipped": self.existing_barcodes_skipped,
                "validation_failures": self.validation_failures,
                "generation_failures": self.generation_failures,
                "elapsed_seconds": self.elapsed_seconds,
                "books_per_second": self.books_per_second,
            },
            "results": [result.to_dict() for result in self.results],
        }

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return (
            f"BatchProcessingResult(total={self.total_processed}, "
            f"generated={self.successful_generations}, "
            f"skipped={self.existing_barcodes_skipped}, "
            f"validation_failures={self.validation_failures}, "
            f"generation_failures={self.generation_failures}, "
            f"elapsed_seconds={self.elapsed_seconds!r})"
        )


@dataclass(frozen=True, slots=True)
class ImportWarning:
    """Recoverable import issue with enough context for diagnostics.

    Immutable value object — treat instances as read-only after construction.

    Attributes:
        message: Human-readable description of the issue.
        row_number: 1-based worksheet row when applicable.
        code: Optional short machine-readable code (e.g. ``missing_isbn``).
    """

    message: str
    row_number: int | None = None
    code: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize this warning to a JSON-compatible dictionary."""
        return {
            "message": self.message,
            "row_number": self.row_number,
            "code": self.code,
        }

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return (
            f"ImportWarning(row_number={self.row_number!r}, "
            f"code={self.code!r}, message={self.message!r})"
        )


@dataclass(frozen=True, slots=True)
class ImportResult:
    """Outcome of importing books from a workbook.

    Immutable value object — treat instances as read-only after construction.
    Nested lists are not deep-frozen; callers should not mutate them.

    Attributes:
        books: Successfully mapped :class:`Book` instances (input/sheet order).
        source_rows: 1-based worksheet row for each entry in ``books``.
        total_rows: Data rows examined after the header (including blanks).
        imported_rows: Count of successfully imported books.
        skipped_rows: Count of blank or rejected data rows.
        warnings: Recoverable issues with row context.
        elapsed_seconds: Wall-clock duration of the import.
        workbook_path: Workbook that was imported, when known.
        worksheet_name: Worksheet that was read, when known.
    """

    books: list[Book] = field(default_factory=list)
    source_rows: list[int] = field(default_factory=list)
    total_rows: int = 0
    imported_rows: int = 0
    skipped_rows: int = 0
    warnings: list[ImportWarning] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    workbook_path: Path | None = None
    worksheet_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize import results to a JSON-compatible dictionary."""
        return {
            "summary": {
                "total_rows": self.total_rows,
                "imported_rows": self.imported_rows,
                "skipped_rows": self.skipped_rows,
                "warning_count": len(self.warnings),
                "elapsed_seconds": self.elapsed_seconds,
            },
            "workbook_path": str(self.workbook_path) if self.workbook_path else None,
            "worksheet_name": self.worksheet_name,
            "source_rows": list(self.source_rows),
            "books": [book.to_dict() for book in self.books],
            "warnings": [warning.to_dict() for warning in self.warnings],
        }

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return (
            f"ImportResult(imported={self.imported_rows}, "
            f"skipped={self.skipped_rows}, warnings={len(self.warnings)}, "
            f"elapsed_seconds={self.elapsed_seconds!r})"
        )


@dataclass(frozen=True, slots=True)
class LabelLayoutWarning:
    """Recoverable layout issue with diagnostic context.

    Attributes:
        message: Human-readable description.
        isbn: ISBN related to the warning, when applicable.
        page_number: 1-based page when applicable.
        code: Short machine-readable code.
    """

    message: str
    isbn: str | None = None
    page_number: int | None = None
    code: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize this warning to a JSON-compatible dictionary."""
        return {
            "message": self.message,
            "isbn": self.isbn,
            "page_number": self.page_number,
            "code": self.code,
        }


@dataclass(frozen=True, slots=True)
class LabelLayoutResult:
    """Outcome of arranging books onto label worksheet pages.

    Immutable value object — treat instances as read-only after construction.

    Attributes:
        pages_created: Number of worksheet pages created.
        labels_placed: Number of labels successfully placed.
        empty_labels_remaining_on_last_page: Unused slots on the final page.
        elapsed_seconds: Wall-clock duration of the layout run.
        warnings: Recoverable issues encountered during layout.
        template_id: Template used for layout.
    """

    pages_created: int = 0
    labels_placed: int = 0
    empty_labels_remaining_on_last_page: int = 0
    elapsed_seconds: float = 0.0
    warnings: tuple[LabelLayoutWarning, ...] = ()
    template_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize layout results to a JSON-compatible dictionary."""
        return {
            "summary": {
                "pages_created": self.pages_created,
                "labels_placed": self.labels_placed,
                "empty_labels_remaining_on_last_page": (
                    self.empty_labels_remaining_on_last_page
                ),
                "elapsed_seconds": self.elapsed_seconds,
                "warning_count": len(self.warnings),
                "template_id": self.template_id,
            },
            "warnings": [warning.to_dict() for warning in self.warnings],
        }

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return (
            f"LabelLayoutResult(pages={self.pages_created}, "
            f"labels={self.labels_placed}, "
            f"empty_remaining={self.empty_labels_remaining_on_last_page}, "
            f"elapsed_seconds={self.elapsed_seconds!r})"
        )


@dataclass(frozen=True, slots=True)
class WorkbookGenerationWarning:
    """Recoverable issue during end-to-end workbook generation.

    Attributes:
        message: Human-readable description.
        code: Short machine-readable code.
        isbn: Related ISBN when applicable.
        row_number: Related worksheet row when applicable.
        page_number: Related label page when applicable.
    """

    message: str
    code: str = ""
    isbn: str | None = None
    row_number: int | None = None
    page_number: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize this warning to a JSON-compatible dictionary."""
        return {
            "message": self.message,
            "code": self.code,
            "isbn": self.isbn,
            "row_number": self.row_number,
            "page_number": self.page_number,
        }


@dataclass(frozen=True, slots=True)
class WorkbookGenerationResult:
    """Outcome of generating a printable label workbook from inventory.

    Immutable value object — treat instances as read-only after construction.

    Attributes:
        books_imported: Books successfully imported from the inventory workbook.
        books_processed: Books passed through batch processing.
        labels_created: Labels placed by the layout engine.
        pages_created: Label worksheet pages created.
        barcodes_generated: Newly generated barcode PNG files.
        barcodes_reused: Existing barcode PNG files reused.
        output_path: Path to the saved label workbook.
        elapsed_seconds: Wall-clock duration of the full run.
        warnings: Recoverable issues from import, batch, or layout.
    """

    books_imported: int = 0
    books_processed: int = 0
    labels_created: int = 0
    pages_created: int = 0
    barcodes_generated: int = 0
    barcodes_reused: int = 0
    output_path: Path | None = None
    elapsed_seconds: float = 0.0
    warnings: tuple[WorkbookGenerationWarning, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize generation results to a JSON-compatible dictionary."""
        return {
            "summary": {
                "books_imported": self.books_imported,
                "books_processed": self.books_processed,
                "labels_created": self.labels_created,
                "pages_created": self.pages_created,
                "barcodes_generated": self.barcodes_generated,
                "barcodes_reused": self.barcodes_reused,
                "output_path": str(self.output_path) if self.output_path else None,
                "elapsed_seconds": self.elapsed_seconds,
                "warning_count": len(self.warnings),
            },
            "warnings": [warning.to_dict() for warning in self.warnings],
        }

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return (
            f"WorkbookGenerationResult(imported={self.books_imported}, "
            f"labels={self.labels_created}, pages={self.pages_created}, "
            f"output_path={self.output_path!r}, "
            f"elapsed_seconds={self.elapsed_seconds!r})"
        )


@dataclass(slots=True)
class ApplicationSettings:
    """Project-wide and per-run application settings.

    Attributes:
        barcode_output_directory: Directory for generated barcode PNG files.
        log_directory: Directory for application log files.
        template_directory: Directory for label templates.
        default_label_type: Deprecated compatibility field. Not used by
            LabelLayoutService. Prefer ``label_template_id``.
        app_version: Component version string from the ``VERSION`` file.
        project_root: Root of the ``barcode_generator`` project directory.
        input_path: Optional path to the input books JSON for a run.
        results_path: Optional path for the results JSON for a run.
        overwrite: When True, regenerate PNGs even if they already exist.
        log_level: Logging level name.
        log_file: Optional explicit log file path (defaults under ``log_directory``).
        barcode_module_width: Barcode bar module width in millimeters.
        barcode_module_height: Barcode bar module height in millimeters.
        barcode_quiet_zone: Quiet-zone margin in millimeters.
        barcode_font_size: Human-readable text font size (points).
        barcode_dpi: Output image resolution in dots per inch.
        workbook_path: Optional Excel workbook path for import.
        workbook_sheet_name: Worksheet name to import.
        workbook_column_isbn: Header name for the ISBN column.
        workbook_column_title: Header name for the title column.
        workbook_column_author: Header name for the author column.
        workbook_column_copies: Header name for the copies column.
        workbook_header_row: 1-based header row index.
        label_template_id: Single source of truth for the registered label
            template id (e.g. ``avery-5160``). Used by LabelLayoutService.
    """

    barcode_output_directory: Path
    log_directory: Path
    template_directory: Path
    default_label_type: str
    app_version: str
    project_root: Path
    input_path: Path | None = None
    results_path: Path | None = None
    overwrite: bool = False
    log_level: str = "INFO"
    log_file: Path | None = None
    barcode_module_width: float = DEFAULT_BARCODE_MODULE_WIDTH
    barcode_module_height: float = DEFAULT_BARCODE_MODULE_HEIGHT
    barcode_quiet_zone: float = DEFAULT_BARCODE_QUIET_ZONE
    barcode_font_size: int = DEFAULT_BARCODE_FONT_SIZE
    barcode_dpi: int = DEFAULT_BARCODE_DPI
    workbook_path: Path | None = None
    workbook_sheet_name: str = DEFAULT_WORKBOOK_SHEET_NAME
    workbook_column_isbn: str = DEFAULT_WORKBOOK_COLUMN_ISBN
    workbook_column_title: str = DEFAULT_WORKBOOK_COLUMN_TITLE
    workbook_column_author: str = DEFAULT_WORKBOOK_COLUMN_AUTHOR
    workbook_column_copies: str = DEFAULT_WORKBOOK_COLUMN_COPIES
    workbook_header_row: int = DEFAULT_WORKBOOK_HEADER_ROW
    label_template_id: str = DEFAULT_LABEL_TEMPLATE_ID

    def __post_init__(self) -> None:
        """Normalize path fields to :class:`~pathlib.Path` instances."""
        self.barcode_output_directory = Path(self.barcode_output_directory)
        self.log_directory = Path(self.log_directory)
        self.template_directory = Path(self.template_directory)
        self.project_root = Path(self.project_root)
        if self.input_path is not None:
            self.input_path = Path(self.input_path)
        if self.results_path is not None:
            self.results_path = Path(self.results_path)
        if self.log_file is not None:
            self.log_file = Path(self.log_file)
        if self.workbook_path is not None:
            self.workbook_path = Path(self.workbook_path)
        if not self.app_version.strip():
            raise ValueError("app_version must not be empty")
        if not self.default_label_type.strip():
            raise ValueError("default_label_type must not be empty")
        if not self.label_template_id.strip():
            raise ValueError("label_template_id must not be empty")
        if self.barcode_module_width <= 0:
            raise ValueError("barcode_module_width must be positive")
        if self.barcode_module_height <= 0:
            raise ValueError("barcode_module_height must be positive")
        if self.barcode_quiet_zone < 0:
            raise ValueError("barcode_quiet_zone must be non-negative")
        if self.barcode_font_size <= 0:
            raise ValueError("barcode_font_size must be positive")
        if self.barcode_dpi <= 0:
            raise ValueError("barcode_dpi must be positive")
        if not self.workbook_sheet_name.strip():
            raise ValueError("workbook_sheet_name must not be empty")
        if self.workbook_header_row < 1:
            raise ValueError("workbook_header_row must be >= 1")
        for name, value in (
            ("workbook_column_isbn", self.workbook_column_isbn),
            ("workbook_column_title", self.workbook_column_title),
            ("workbook_column_author", self.workbook_column_author),
            ("workbook_column_copies", self.workbook_column_copies),
        ):
            if not str(value).strip():
                raise ValueError(f"{name} must not be empty")

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return (
            f"ApplicationSettings(version={self.app_version!r}, "
            f"barcode_output_directory={self.barcode_output_directory!r}, "
            f"log_directory={self.log_directory!r}, "
            f"default_label_type={self.default_label_type!r})"
        )


# --- Extension-point models (future features) ---------------------------------


@dataclass(slots=True)
class IsbnLookupResult:
    """Result model for future ISBN metadata lookup providers.

    Attributes:
        isbn: Queried ISBN.
        title: Resolved title, if found.
        author: Resolved author, if found.
        raw: Provider-specific payload for debugging / caching.

    Note:
        Lookup providers are not implemented yet; this model reserves the
        contract for Sprint+ enrichment work.
    """

    isbn: str
    title: str | None = None
    author: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return f"IsbnLookupResult(isbn={self.isbn!r}, title={self.title!r})"


@dataclass(slots=True)
class CoverImageResult:
    """Result model for future cover image download providers.

    Attributes:
        isbn: ISBN associated with the cover.
        image_path: Local path to the downloaded cover image.
        source_url: Remote URL the cover was fetched from.

    Note:
        Cover download providers are not implemented yet; this model reserves
        the contract for future enrichment work.
    """

    isbn: str
    image_path: Path | None = None
    source_url: str | None = None

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return f"CoverImageResult(isbn={self.isbn!r}, image_path={self.image_path!r})"


def _optional_str(value: Any) -> str | None:
    """Convert an optional raw value to ``str`` or ``None``."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None
