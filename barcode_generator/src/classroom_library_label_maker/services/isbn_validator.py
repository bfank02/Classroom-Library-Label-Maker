"""ISBN-13 normalization and validation for classroom library books.

This module is intentionally limited to normalization and validation. It does
not generate barcodes or interact with workbooks.

Stable public API (frozen)
--------------------------
The following methods are the stable ISBN validation interface and should
remain backward compatible unless a major version change occurs:

* :meth:`IsbnValidator.normalize` — clean an ISBN string without validating
* :meth:`IsbnValidator.validate` — validate one ISBN; always returns
  :class:`~classroom_library_label_maker.models.ValidationResult`
* :meth:`IsbnValidator.validate_many` — validate an iterable via ``validate``

Additional public helpers (not part of the frozen surface above):

* :meth:`IsbnValidator.is_valid` — convenience boolean wrapper
* :meth:`IsbnValidator.compute_check_digit` — ISBN-13 / EAN-13 check digit

``validate`` accepts ISBN-10 or ISBN-13. Valid ISBN-10 values are converted to
ISBN-13 (``978`` + body) so callers always receive an ISBN-13 on success.
"""

from __future__ import annotations

from collections.abc import Iterable

from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.models import ValidationErrorCode, ValidationResult

_logger = get_logger("isbn_validator")

_VALID_PREFIXES: frozenset[str] = frozenset({"978", "979"})
_ISBN13_LENGTH = 13
_ISBN10_LENGTH = 10


class IsbnValidator:
    """Stateless ISBN-10 / ISBN-13 normalizer and validator.

    Expected validation failures are returned as :class:`ValidationResult`
    values; this class does not raise for invalid ISBN input.

    User-facing failure text comes from
    :attr:`ValidationErrorCode.message` so messages stay centralized.
    """

    def normalize(self, isbn: str | None) -> str:
        """Return a normalized ISBN string without validating it.

        This is a public helper for callers that need a cleaned value (for
        display, deduplication, or file naming) before or instead of full
        validation.

        Accepts ``None`` or ``str``. Trims leading/trailing whitespace, then
        removes internal spaces and hyphens. Other characters are left in place
        so :meth:`validate` can report ``NON_NUMERIC`` when appropriate.
        A trailing ISBN-10 check digit ``x`` / ``X`` is uppercased.

        Args:
            isbn: Raw ISBN value, or ``None``.

        Returns:
            Normalized string (possibly empty). Does **not** check length,
            prefix, or checksum.
        """
        if isbn is None:
            return ""
        trimmed = isbn.strip()
        cleaned = trimmed.replace("-", "").replace(" ", "")
        if (
            len(cleaned) == _ISBN10_LENGTH
            and cleaned[:9].isdigit()
            and cleaned[9] in "xX"
        ):
            return cleaned[:9] + "X"
        return cleaned

    def validate(self, isbn: str | None) -> ValidationResult:
        """Validate an ISBN-10 or ISBN-13 value and return a structured result.

        ISBN-10 inputs that pass the ISBN-10 check digit are converted to
        ISBN-13 before the ISBN-13 rules below. Successful results always
        carry an ISBN-13 in :attr:`ValidationResult.isbn`.

        Validation order (after optional ISBN-10 conversion):

        1. Empty input
        2. Numeric characters only
        3. Exactly 13 digits
        4. Prefix ``978`` or ``979``
        5. ISBN-13 checksum

        Args:
            isbn: Raw ISBN value, or ``None``.

        Returns:
            A :class:`ValidationResult` for every attempt.
        """
        normalized = self.normalize(isbn)

        if self._is_empty(normalized):
            return self._invalid_result(
                isbn="",
                code=ValidationErrorCode.EMPTY,
            )

        if self._looks_like_isbn10(normalized):
            converted = self._isbn10_to_isbn13(normalized)
            if converted is None:
                return self._invalid_result(
                    isbn=normalized,
                    code=ValidationErrorCode.INVALID_CHECKSUM,
                )
            normalized = converted

        if not self._is_numeric(normalized):
            return self._invalid_result(
                isbn=normalized,
                code=ValidationErrorCode.NON_NUMERIC,
            )

        if not self._has_valid_length(normalized):
            return self._invalid_result(
                isbn=normalized,
                code=ValidationErrorCode.INVALID_LENGTH,
            )

        if not self._has_valid_prefix(normalized):
            return self._invalid_result(
                isbn=normalized,
                code=ValidationErrorCode.INVALID_PREFIX,
            )

        if not self._checksum_is_valid(normalized):
            return self._invalid_result(
                isbn=normalized,
                code=ValidationErrorCode.INVALID_CHECKSUM,
            )

        _logger.debug("Validated ISBN-13: %s", normalized)
        return ValidationResult(
            isbn=normalized,
            is_valid=True,
            errors=[],
            error_code=ValidationErrorCode.NONE,
        )

    def validate_many(
        self,
        isbns: Iterable[str | None],
    ) -> list[ValidationResult]:
        """Validate multiple ISBN values in order.

        Reuses :meth:`validate` for each item; validation rules are not
        duplicated here.

        Args:
            isbns: Iterable of raw ISBN values (each may be ``None`` or ``str``).

        Returns:
            A list of :class:`ValidationResult` objects in the same order as
            ``isbns``.
        """
        return [self.validate(value) for value in isbns]

    def is_valid(self, isbn: str | None) -> bool:
        """Return whether ``isbn`` is a valid ISBN-10 or ISBN-13.

        Args:
            isbn: Raw ISBN value, or ``None``.

        Returns:
            ``True`` if valid; otherwise ``False``.
        """
        return self.validate(isbn).is_valid

    def compute_check_digit(self, first_twelve_digits: str) -> str:
        """Compute the ISBN-13 / EAN-13 check digit for 12 digits.

        Args:
            first_twelve_digits: Exactly twelve digit characters.

        Returns:
            A single check-digit character from ``"0"`` to ``"9"``.

        Raises:
            ValueError: If ``first_twelve_digits`` is not twelve digits.
        """
        if len(first_twelve_digits) != 12 or not first_twelve_digits.isdigit():
            raise ValueError(
                "first_twelve_digits must be exactly 12 numeric characters"
            )
        total = 0
        for index, char in enumerate(first_twelve_digits):
            weight = 1 if index % 2 == 0 else 3
            total += int(char) * weight
        check = (10 - (total % 10)) % 10
        return str(check)

    def _is_empty(self, normalized: str) -> bool:
        """Return whether normalized input is empty."""
        return normalized == ""

    def _is_numeric(self, normalized: str) -> bool:
        """Return whether normalized input contains only digit characters."""
        return normalized.isdigit()

    def _has_valid_length(self, normalized: str) -> bool:
        """Return whether normalized input has ISBN-13 length."""
        return len(normalized) == _ISBN13_LENGTH

    def _has_valid_prefix(self, normalized: str) -> bool:
        """Return whether normalized input starts with 978 or 979."""
        return normalized[:3] in _VALID_PREFIXES

    def _checksum_is_valid(self, isbn13: str) -> bool:
        """Return whether the ISBN-13 check digit is correct."""
        expected = self.compute_check_digit(isbn13[:12])
        return isbn13[12] == expected

    def _looks_like_isbn10(self, normalized: str) -> bool:
        """True when normalized input is shaped like an ISBN-10."""
        if len(normalized) != _ISBN10_LENGTH:
            return False
        body, check = normalized[:9], normalized[9]
        return body.isdigit() and (check.isdigit() or check == "X")

    def _isbn10_check_is_valid(self, isbn10: str) -> bool:
        """Return whether an ISBN-10 check character is correct."""
        if not self._looks_like_isbn10(isbn10):
            return False
        total = sum(
            (10 - index) * int(digit) for index, digit in enumerate(isbn10[:9])
        )
        remainder = total % 11
        expected = (11 - remainder) % 11
        expected_char = "X" if expected == 10 else str(expected)
        return isbn10[9] == expected_char

    def _isbn10_to_isbn13(self, isbn10: str) -> str | None:
        """Convert a valid ISBN-10 to ISBN-13, or ``None`` if invalid."""
        if not self._isbn10_check_is_valid(isbn10):
            return None
        core = f"978{isbn10[:9]}"
        return f"{core}{self.compute_check_digit(core)}"

    def _invalid_result(
        self,
        *,
        isbn: str,
        code: ValidationErrorCode,
    ) -> ValidationResult:
        """Build an invalid :class:`ValidationResult` using ``code.message``."""
        message = code.message
        return ValidationResult(
            isbn=isbn,
            is_valid=False,
            errors=[message] if message else [],
            error_code=code,
        )


# Alias matching the feature brief / common branding capitalization.
ISBNValidator = IsbnValidator
