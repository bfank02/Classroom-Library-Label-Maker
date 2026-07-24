"""Tests for batch processing orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from classroom_library_label_maker.models import (
    ApplicationSettings,
    BarcodeGenerationResult,
    BarcodeStatus,
    BatchResults,
    Book,
    ValidationResult,
)
from classroom_library_label_maker.services.batch_processor import BatchProcessor


def test_process_book_invalid_isbn(
    app_settings: ApplicationSettings,
    sample_book: Book,
) -> None:
    """Invalid ISBNs should yield INVALID_ISBN without calling the generator."""
    validator = MagicMock()
    validator.validate.return_value = ValidationResult(
        isbn=sample_book.isbn,
        is_valid=False,
        errors=["bad isbn"],
    )
    generator = MagicMock()
    processor = BatchProcessor(
        app_settings,
        validator=validator,
        generator=generator,
    )

    result = processor.process_book(sample_book)

    assert result.status == BarcodeStatus.INVALID_ISBN
    assert result.message == "bad isbn"
    generator.generate_if_missing.assert_not_called()


def test_process_book_generated(
    app_settings: ApplicationSettings,
    sample_book: Book,
) -> None:
    """Valid ISBN with new image should yield GENERATED."""
    validator = MagicMock()
    validator.validate.return_value = ValidationResult(
        isbn="9780064400558",
        is_valid=True,
        errors=[],
    )
    generator = MagicMock()
    output = app_settings.barcode_output_directory / "9780064400558.png"
    generator.generate_if_missing.return_value = (output, True)
    processor = BatchProcessor(
        app_settings,
        validator=validator,
        generator=generator,
    )

    result = processor.process_book(sample_book)

    assert result.status == BarcodeStatus.GENERATED
    assert result.output_path == output


def test_process_book_already_exists(
    app_settings: ApplicationSettings,
    sample_book: Book,
) -> None:
    """Existing barcode should yield ALREADY_EXISTS."""
    validator = MagicMock()
    validator.validate.return_value = ValidationResult(
        isbn="9780064400558",
        is_valid=True,
        errors=[],
    )
    generator = MagicMock()
    output = app_settings.barcode_output_directory / "9780064400558.png"
    generator.generate_if_missing.return_value = (output, False)
    processor = BatchProcessor(
        app_settings,
        validator=validator,
        generator=generator,
    )

    result = processor.process_book(sample_book)

    assert result.status == BarcodeStatus.ALREADY_EXISTS


def test_write_results_creates_json(
    app_settings: ApplicationSettings,
    tmp_path: Path,
) -> None:
    """write_results should create a JSON file with a summary section."""
    processor = BatchProcessor(app_settings)
    batch = BatchResults(
        results=[
            BarcodeGenerationResult(
                "9780064400558",
                BarcodeStatus.GENERATED,
                title="Demo",
            ),
        ],
        input_path=app_settings.input_path,
        output_dir=app_settings.barcode_output_directory,
    )
    results_path = tmp_path / "out" / "results.json"
    processor.write_results(batch, results_path)

    assert results_path.is_file()
    text = results_path.read_text(encoding="utf-8")
    assert '"generated": 1' in text


@pytest.mark.xfail(reason="JSON loading not implemented yet", strict=True)
def test_load_books_not_implemented(app_settings: ApplicationSettings) -> None:
    """load_books should eventually parse JSON into Book objects."""
    assert app_settings.input_path is not None
    processor = BatchProcessor(app_settings)
    app_settings.input_path.write_text(
        '[{"isbn": "9780064400558", "title": "A", "author": "B", "copies": 1}]',
        encoding="utf-8",
    )
    books = processor.load_books(app_settings.input_path)
    assert len(books) == 1
