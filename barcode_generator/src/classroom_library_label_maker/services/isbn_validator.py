"""ISBN-13 validation for classroom library books."""

from __future__ import annotations

import re

from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.models import ValidationResult

_logger = get_logger("isbn_validator")

_ISBN13_DIGITS = re.compile(r"^\d{13}$")
_NON_DIGIT = re.compile(r"[^0-9]")


class IsbnValidator:
    """Validate and normalize ISBN-13 identifiers.

    Designed so future ISBN-10 conversion and remote enrichment can plug in
    without changing call sites that depend on :meth:`validate`.
    """

    def normalize(self, isbn: str) -> str:
        """Strip hyphens/spaces and return digits only.

        Args:
            isbn: Raw ISBN string from input data.

        Returns:
            A string containing only digit characters.
        """
        return _NON_DIGIT.sub("", isbn.strip())

    def validate(self, isbn: str) -> ValidationResult:
        """Validate an ISBN-13 value including check digit.

        Args:
            isbn: Raw ISBN string (may include hyphens or spaces).

        Returns:
            A :class:`ValidationResult` describing validity.
        """
        original = isbn
        normalized = self.normalize(isbn)

        if not normalized:
            return ValidationResult(
                isbn=original,
                is_valid=False,
                errors=["ISBN is empty"],
            )

        if not _ISBN13_DIGITS.match(normalized):
            return ValidationResult(
                isbn=normalized,
                is_valid=False,
                errors=["ISBN-13 must contain exactly 13 digits"],
            )

        try:
            check_ok = self._check_digit_is_valid(normalized)
        except NotImplementedError:
            # Check-digit algorithm is intentionally unimplemented until the
            # barcode engine sprint delivers validation logic.
            raise

        if not check_ok:
            return ValidationResult(
                isbn=normalized,
                is_valid=False,
                errors=["ISBN-13 check digit is invalid"],
            )

        # ISBN-10 acceptance / conversion will be added when inventory import
        # requirements are finalized.
        _logger.debug("Validated ISBN-13: %s", normalized)
        return ValidationResult(isbn=normalized, is_valid=True, errors=[])

    def is_valid(self, isbn: str) -> bool:
        """Return whether ``isbn`` is a valid ISBN-13.

        Args:
            isbn: Raw ISBN string.

        Returns:
            ``True`` if valid; otherwise ``False``.
        """
        return self.validate(isbn).is_valid

    def _check_digit_is_valid(self, isbn13: str) -> bool:
        """Verify the EAN-13 / ISBN-13 check digit.

        Args:
            isbn13: A 13-digit string.

        Returns:
            ``True`` if the check digit matches the computed value.

        Raises:
            NotImplementedError: Until the GS1 check-digit algorithm is added.
        """
        # Weighted sum of first 12 digits (weights 1 and 3 alternating);
        # check digit = (10 - (sum % 10)) % 10. Deferred to feature work.
        _ = isbn13
        raise NotImplementedError("ISBN-13 check digit validation is not implemented")
