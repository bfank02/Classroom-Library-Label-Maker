"""Tests for ISBN-13 validation."""

from __future__ import annotations

import pytest

from classroom_library_label_maker.models import ValidationErrorCode
from classroom_library_label_maker.services.isbn_validator import (
    ISBNValidator,
    IsbnValidator,
)


@pytest.fixture
def validator() -> IsbnValidator:
    """Return a fresh :class:`IsbnValidator`."""
    return IsbnValidator()


# --- Normalization ------------------------------------------------------------


def test_normalize_strips_hyphens(validator: IsbnValidator) -> None:
    """Hyphens should be removed during normalization."""
    assert validator.normalize("978-0-06-440055-8") == "9780064400558"


def test_normalize_strips_spaces(validator: IsbnValidator) -> None:
    """Internal spaces should be removed during normalization."""
    assert validator.normalize("978 006 440055 8") == "9780064400558"


def test_normalize_trims_whitespace(validator: IsbnValidator) -> None:
    """Leading and trailing whitespace should be trimmed."""
    assert validator.normalize("  9780064400558  ") == "9780064400558"


def test_normalize_none_returns_empty(validator: IsbnValidator) -> None:
    """``None`` should normalize to an empty string."""
    assert validator.normalize(None) == ""


def test_normalize_preserves_non_digit_characters(validator: IsbnValidator) -> None:
    """Letters and other symbols remain so validation can report NON_NUMERIC."""
    assert validator.normalize("978-ISBN-123") == "978ISBN123"


# --- Valid ISBNs --------------------------------------------------------------


def test_validate_accepts_known_good_isbn(validator: IsbnValidator) -> None:
    """A known-good ISBN-13 should validate."""
    result = validator.validate("9780064400558")
    assert result.is_valid is True
    assert result.isbn == "9780064400558"
    assert result.error_code == ValidationErrorCode.NONE
    assert result.errors == []


def test_validate_accepts_hyphenated_isbn(validator: IsbnValidator) -> None:
    """Hyphenated ISBN-13 values should validate after normalization."""
    result = validator.validate("978-0-06-440055-8")
    assert result.is_valid is True
    assert result.isbn == "9780064400558"
    assert result.error_code == ValidationErrorCode.NONE


def test_validate_accepts_space_separated_isbn(validator: IsbnValidator) -> None:
    """Space-separated ISBN-13 values should validate after normalization."""
    result = validator.validate("978 0 06 440055 8")
    assert result.is_valid is True
    assert result.isbn == "9780064400558"


def test_validate_accepts_leading_trailing_whitespace(
    validator: IsbnValidator,
) -> None:
    """Surrounding whitespace should not prevent a valid ISBN from passing."""
    result = validator.validate("  9780064400558\n")
    assert result.is_valid is True
    assert result.isbn == "9780064400558"


def test_validate_accepts_979_prefix(validator: IsbnValidator) -> None:
    """ISBNs with a 979 prefix and valid checksum should pass."""
    # 9791234567896 — constructed with a valid check digit.
    body = "979123456789"
    check = validator.compute_check_digit(body)
    isbn = body + check
    result = validator.validate(isbn)
    assert result.is_valid is True
    assert result.isbn == isbn
    assert isbn.startswith("979")


def test_is_valid_true_for_good_isbn(validator: IsbnValidator) -> None:
    """is_valid should return True for a valid ISBN-13."""
    assert validator.is_valid("978-0-06-440055-8") is True


def test_isbn_validator_alias() -> None:
    """ISBNValidator should be an alias of IsbnValidator."""
    assert ISBNValidator is IsbnValidator


# --- Invalid cases ------------------------------------------------------------


def test_validate_rejects_empty_string(validator: IsbnValidator) -> None:
    """Empty string should return EMPTY."""
    result = validator.validate("")
    assert result.is_valid is False
    assert result.error_code == ValidationErrorCode.EMPTY
    assert result.isbn == ""
    assert result.errors


def test_validate_rejects_whitespace_only(validator: IsbnValidator) -> None:
    """Whitespace-only input should return EMPTY."""
    result = validator.validate("   \t  ")
    assert result.is_valid is False
    assert result.error_code == ValidationErrorCode.EMPTY


def test_validate_rejects_none(validator: IsbnValidator) -> None:
    """``None`` should return EMPTY."""
    result = validator.validate(None)
    assert result.is_valid is False
    assert result.error_code == ValidationErrorCode.EMPTY
    assert result.isbn == ""


def test_validate_rejects_non_numeric(validator: IsbnValidator) -> None:
    """Letters in the ISBN should return NON_NUMERIC."""
    result = validator.validate("978006440055X")
    assert result.is_valid is False
    assert result.error_code == ValidationErrorCode.NON_NUMERIC
    assert result.isbn == "978006440055X"


def test_validate_rejects_non_numeric_with_hyphens(
    validator: IsbnValidator,
) -> None:
    """Non-numeric characters remain after hyphen removal."""
    result = validator.validate("978-0-06-HELLO-8")
    assert result.is_valid is False
    assert result.error_code == ValidationErrorCode.NON_NUMERIC


def test_validate_rejects_too_short(validator: IsbnValidator) -> None:
    """Fewer than 13 digits should return INVALID_LENGTH."""
    result = validator.validate("978006440055")
    assert result.is_valid is False
    assert result.error_code == ValidationErrorCode.INVALID_LENGTH
    assert result.isbn == "978006440055"


def test_validate_rejects_too_long(validator: IsbnValidator) -> None:
    """More than 13 digits should return INVALID_LENGTH."""
    result = validator.validate("97800644005581")
    assert result.is_valid is False
    assert result.error_code == ValidationErrorCode.INVALID_LENGTH


def test_validate_rejects_invalid_prefix(validator: IsbnValidator) -> None:
    """Prefixes other than 978/979 should return INVALID_PREFIX."""
    # 12 digits of payload + computed check so only the prefix fails.
    body = "977123456789"
    check = validator.compute_check_digit(body)
    result = validator.validate(body + check)
    assert result.is_valid is False
    assert result.error_code == ValidationErrorCode.INVALID_PREFIX


def test_validate_rejects_invalid_checksum(validator: IsbnValidator) -> None:
    """Wrong check digit should return INVALID_CHECKSUM."""
    result = validator.validate("9780064400550")
    assert result.is_valid is False
    assert result.error_code == ValidationErrorCode.INVALID_CHECKSUM
    assert result.isbn == "9780064400550"


def test_is_valid_false_for_bad_isbn(validator: IsbnValidator) -> None:
    """is_valid should return False for an invalid ISBN."""
    assert validator.is_valid("9780064400550") is False


# --- Helpers ------------------------------------------------------------------


def test_compute_check_digit_known_value(validator: IsbnValidator) -> None:
    """compute_check_digit should match a known ISBN-13 check digit."""
    assert validator.compute_check_digit("978006440055") == "8"


def test_compute_check_digit_rejects_bad_input(validator: IsbnValidator) -> None:
    """compute_check_digit should reject non-12-digit input."""
    with pytest.raises(ValueError, match="12 numeric"):
        validator.compute_check_digit("97800644005")
    with pytest.raises(ValueError, match="12 numeric"):
        validator.compute_check_digit("97800644005X")


def test_validation_order_empty_before_non_numeric(
    validator: IsbnValidator,
) -> None:
    """Empty input should be reported as EMPTY, not NON_NUMERIC."""
    result = validator.validate(None)
    assert result.error_code == ValidationErrorCode.EMPTY


def test_validation_order_non_numeric_before_length(
    validator: IsbnValidator,
) -> None:
    """Non-numeric should win over length when both could apply."""
    result = validator.validate("978ABC")
    assert result.error_code == ValidationErrorCode.NON_NUMERIC


def test_validation_order_length_before_prefix(validator: IsbnValidator) -> None:
    """Invalid length should be reported before prefix checks."""
    result = validator.validate("977123")
    assert result.error_code == ValidationErrorCode.INVALID_LENGTH


def test_second_known_valid_isbn(validator: IsbnValidator) -> None:
    """Another published ISBN-13 should validate."""
    result = validator.validate("9780060256654")
    assert result.is_valid is True
    assert result.error_code == ValidationErrorCode.NONE


# --- Public helpers: normalize / validate_many / messages ---------------------


def test_normalize_does_not_validate(validator: IsbnValidator) -> None:
    """normalize should clean input without enforcing ISBN-13 rules."""
    assert validator.normalize("977-12") == "97712"
    assert validator.normalize("978-0-06-440055-0") == "9780064400550"


def test_validate_many_returns_ordered_results(validator: IsbnValidator) -> None:
    """validate_many should map each input through validate() in order."""
    values = [
        "9780064400558",
        None,
        "9780064400550",
        "978-0-06-440055-8",
    ]
    results = validator.validate_many(values)
    assert len(results) == 4
    assert results[0].is_valid is True
    assert results[1].error_code == ValidationErrorCode.EMPTY
    assert results[2].error_code == ValidationErrorCode.INVALID_CHECKSUM
    assert results[3].is_valid is True
    assert results[3].isbn == "9780064400558"


def test_validate_many_empty_iterable(validator: IsbnValidator) -> None:
    """validate_many on an empty iterable should return an empty list."""
    assert validator.validate_many([]) == []


def test_error_messages_come_from_error_code(validator: IsbnValidator) -> None:
    """ValidationResult.errors should use ValidationErrorCode.message."""
    cases = [
        (None, ValidationErrorCode.EMPTY),
        ("978006440055X", ValidationErrorCode.NON_NUMERIC),
        ("978006440055", ValidationErrorCode.INVALID_LENGTH),
        ("9771234567890", ValidationErrorCode.INVALID_PREFIX),
        ("9780064400550", ValidationErrorCode.INVALID_CHECKSUM),
    ]
    for raw, code in cases:
        # For INVALID_PREFIX, build a 13-digit value with a valid checksum.
        if code is ValidationErrorCode.INVALID_PREFIX:
            body = "977123456789"
            raw = body + validator.compute_check_digit(body)
        result = validator.validate(raw)
        assert result.error_code is code
        assert result.errors == [code.message]
        assert code.message


def test_none_error_code_has_empty_message() -> None:
    """NONE should expose an empty default message."""
    assert ValidationErrorCode.NONE.message == ""
