"""Domain models for classroom library barcode generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


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


@dataclass(slots=True)
class ValidationResult:
    """Outcome of validating a single ISBN value.

    Attributes:
        isbn: ISBN associated with this result (normalized when valid).
        is_valid: Whether the ISBN passed validation.
        errors: Human-readable validation error messages (empty when valid).
    """

    isbn: str
    is_valid: bool
    errors: list[str] = field(default_factory=list)

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return (
            f"ValidationResult(isbn={self.isbn!r}, is_valid={self.is_valid}, "
            f"errors={self.errors!r})"
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
    """Aggregate results for a full batch processing run.

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


@dataclass(slots=True)
class ApplicationSettings:
    """Project-wide and per-run application settings.

    Attributes:
        barcode_output_directory: Directory for generated barcode PNG files.
        log_directory: Directory for application log files.
        template_directory: Directory for label templates.
        default_label_type: Default label template key (e.g. Avery 5160).
        app_version: Component version string from the ``VERSION`` file.
        project_root: Root of the ``barcode_generator`` project directory.
        input_path: Optional path to the input books JSON for a run.
        results_path: Optional path for the results JSON for a run.
        overwrite: When True, regenerate PNGs even if they already exist.
        log_level: Logging level name.
        log_file: Optional explicit log file path (defaults under ``log_directory``).
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
        if not self.app_version.strip():
            raise ValueError("app_version must not be empty")
        if not self.default_label_type.strip():
            raise ValueError("default_label_type must not be empty")

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
        return (
            f"CoverImageResult(isbn={self.isbn!r}, "
            f"image_path={self.image_path!r})"
        )


def _optional_str(value: Any) -> str | None:
    """Convert an optional raw value to ``str`` or ``None``."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None
