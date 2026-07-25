"""Application-specific exception hierarchy.

These errors are intended for expected failure modes that callers and the CLI
can catch and log cleanly. Unexpected bugs should continue to surface as
ordinary exceptions / tracebacks.
"""

from __future__ import annotations


class ApplicationError(Exception):
    """Base class for all application errors raised by this product.

    Attributes:
        message: Human-readable description suitable for logs and CLI output.
    """

    def __init__(
        self,
        message: str,
        *,
        cause: BaseException | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            message: Description of the failure.
            cause: Optional underlying exception (also set as ``__cause__``).
        """
        super().__init__(message)
        self.message = message
        if cause is not None:
            self.__cause__ = cause

    def __str__(self) -> str:
        """Return the error message."""
        return self.message


class ConfigurationError(ApplicationError):
    """Raised when application settings or project paths are invalid."""


class ValidationError(ApplicationError):
    """Raised when input data fails validation rules."""


class InvalidISBNError(ValidationError):
    """Raised when an ISBN value is missing or structurally invalid."""


class InvalidWorkbookError(ValidationError):
    """Raised when an Excel workbook cannot be read or fails schema checks."""


class BarcodeGenerationError(ApplicationError):
    """Raised when barcode image generation fails for a processable ISBN."""


class FileSystemError(ApplicationError):
    """Raised when required files or directories cannot be read or written."""


class LabelLayoutError(ApplicationError):
    """Raised when label layout fails unrecoverably."""
