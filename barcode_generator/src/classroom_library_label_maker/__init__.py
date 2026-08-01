"""Classroom Library Label Maker — barcode generator package.

Public API exports are intentionally narrow. Prefer importing from the
specific submodules (``models``, ``config``, ``services``, ``exceptions``,
``metadata``) in application code; this package root exposes common types
and version metadata.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from classroom_library_label_maker.exceptions import (
    ApplicationError,
    BarcodeGenerationError,
    ConfigurationError,
    FileSystemError,
    InvalidISBNError,
    InvalidWorkbookError,
    LabelLayoutError,
    ValidationError,
    WorkbookGenerationError,
)
from classroom_library_label_maker.metadata import (
    APP_AUTHOR,
    APP_CLI_NAME,
    APP_DESCRIPTION,
    APP_DISTRIBUTION_NAME,
    APP_LICENSE,
    APP_NAME,
    APP_VERSION,
)
from classroom_library_label_maker.models import (
    ApplicationSettings,
    BarcodeGenerationResult,
    BarcodeStatus,
    BatchProcessingResult,
    Book,
    BookProcessingResult,
    BookProcessingStatus,
    EnrichmentSummary,
    GenerationCompletionState,
    ImportResult,
    ImportWarning,
    LabelContentOptions,
    LabelLayoutResult,
    LabelLayoutWarning,
    ReviewCandidate,
    ReviewItem,
    ValidationErrorCode,
    ValidationResult,
    WorkbookGenerationResult,
    WorkbookGenerationWarning,
)

__all__ = [
    "APP_AUTHOR",
    "APP_CLI_NAME",
    "APP_DESCRIPTION",
    "APP_LICENSE",
    "APP_NAME",
    "APP_VERSION",
    "ApplicationError",
    "ApplicationSettings",
    "BarcodeGenerationError",
    "BarcodeGenerationResult",
    "BarcodeStatus",
    "BatchProcessingResult",
    "Book",
    "BookProcessingResult",
    "BookProcessingStatus",
    "ConfigurationError",
    "EnrichmentSummary",
    "FileSystemError",
    "GenerationCompletionState",
    "ImportResult",
    "ImportWarning",
    "InvalidISBNError",
    "InvalidWorkbookError",
    "LabelContentOptions",
    "LabelLayoutError",
    "LabelLayoutResult",
    "LabelLayoutWarning",
    "ReviewCandidate",
    "ReviewItem",
    "ValidationError",
    "ValidationErrorCode",
    "ValidationResult",
    "WorkbookGenerationError",
    "WorkbookGenerationResult",
    "WorkbookGenerationWarning",
    "__version__",
]

try:
    __version__ = version(APP_DISTRIBUTION_NAME)
except PackageNotFoundError:
    __version__ = APP_VERSION
