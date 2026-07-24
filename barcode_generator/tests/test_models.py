"""Tests for domain models."""

from __future__ import annotations

import pytest

from classroom_library_label_maker.models import (
    BarcodeGenerationResult,
    BarcodeStatus,
    BatchResults,
    Book,
)


def test_book_from_dict_round_trip() -> None:
    """Book serialization should round-trip basic fields."""
    raw = {
        "isbn": "9780060256654",
        "title": "The Giving Tree",
        "author": "Shel Silverstein",
        "copies": 2,
        "genre": "Fiction",
    }
    book = Book.from_dict(raw)
    assert book.isbn == "9780060256654"
    assert book.copies == 2
    assert book.to_dict()["genre"] == "Fiction"


def test_book_accepts_legacy_isbn13_key() -> None:
    """Legacy ``isbn13`` keys should map to ``isbn``."""
    book = Book.from_dict(
        {
            "isbn13": "9780064400558",
            "title": "A",
            "author": "B",
        }
    )
    assert book.isbn == "9780064400558"


def test_book_rejects_empty_isbn() -> None:
    """Empty ISBN values should raise ``ValueError``."""
    with pytest.raises(ValueError, match="isbn"):
        Book(isbn=" ", title="A", author="B")


def test_batch_results_summary_counts() -> None:
    """BatchResults should count generated / skipped / errors."""
    batch = BatchResults(
        results=[
            BarcodeGenerationResult("9780064400558", BarcodeStatus.GENERATED),
            BarcodeGenerationResult("9780060256654", BarcodeStatus.ALREADY_EXISTS),
            BarcodeGenerationResult(
                "000",
                BarcodeStatus.INVALID_ISBN,
                message="bad",
            ),
        ]
    )
    assert batch.generated_count == 1
    assert batch.skipped_count == 1
    assert batch.error_count == 1
    summary = batch.to_dict()["summary"]
    assert summary["total"] == 3
    assert summary["generated"] == 1
