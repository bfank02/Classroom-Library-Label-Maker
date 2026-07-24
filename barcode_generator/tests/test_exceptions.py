"""Tests for the application exception hierarchy."""

from __future__ import annotations

from classroom_library_label_maker.exceptions import (
    ApplicationError,
    BarcodeGenerationError,
    ConfigurationError,
    FileSystemError,
    InvalidISBNError,
    InvalidWorkbookError,
    ValidationError,
)


def test_hierarchy() -> None:
    """Custom exceptions should inherit as documented."""
    assert issubclass(ConfigurationError, ApplicationError)
    assert issubclass(ValidationError, ApplicationError)
    assert issubclass(InvalidISBNError, ValidationError)
    assert issubclass(InvalidWorkbookError, ValidationError)
    assert issubclass(BarcodeGenerationError, ApplicationError)
    assert issubclass(FileSystemError, ApplicationError)


def test_cause_is_preserved() -> None:
    """Optional underlying exceptions should be attached as __cause__."""
    root = ValueError("boom")
    err = ConfigurationError("bad settings", cause=root)
    assert str(err) == "bad settings"
    assert err.__cause__ is root
