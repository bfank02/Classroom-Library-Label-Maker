"""Tests for ISBN-13 validation."""

from __future__ import annotations

import pytest

from classroom_library_label_maker.services.isbn_validator import IsbnValidator


@pytest.fixture
def validator() -> IsbnValidator:
    """Return a fresh :class:`IsbnValidator`."""
    return IsbnValidator()


def test_normalize_strips_hyphens_and_spaces(validator: IsbnValidator) -> None:
    """Normalization should keep digits only."""
    assert validator.normalize("978-0-06-440055-8") == "9780064400558"
    assert validator.normalize("978 006 440055 8") == "9780064400558"


def test_validate_rejects_empty(validator: IsbnValidator) -> None:
    """Empty ISBN should be invalid."""
    result = validator.validate("   ")
    assert result.is_valid is False
    assert any("empty" in error.lower() for error in result.errors)


def test_validate_rejects_wrong_length(validator: IsbnValidator) -> None:
    """Non-13-digit values should be invalid."""
    result = validator.validate("978006440055")
    assert result.is_valid is False
    assert result.isbn == "978006440055"


@pytest.mark.xfail(reason="Check digit algorithm not implemented yet", strict=True)
def test_validate_accepts_known_good_isbn(validator: IsbnValidator) -> None:
    """A known-good ISBN-13 should validate once check digits are implemented."""
    result = validator.validate("978-0-06-440055-8")
    assert result.is_valid is True
    assert result.isbn == "9780064400558"
