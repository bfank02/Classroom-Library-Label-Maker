"""Tests for the batch processing engine."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from classroom_library_label_maker.exceptions import BarcodeGenerationError
from classroom_library_label_maker.models import (
    ApplicationSettings,
    BarcodeGenerationResult,
    BarcodeStatus,
    BatchProcessingResult,
    Book,
    BookProcessingResult,
    BookProcessingStatus,
    ValidationErrorCode,
    ValidationResult,
)
from classroom_library_label_maker.services.batch_processing_service import (
    BatchProcessingService,
)


def _valid_book(
    isbn: str = "9780064400558",
    *,
    title: str = "Charlotte's Web",
) -> Book:
    return Book(isbn=isbn, title=title, author="E. B. White", copies=1)


def _invalid_book() -> Book:
    return Book(isbn="123", title="Bad ISBN Book", author="Someone", copies=1)


@pytest.fixture
def service(app_settings: ApplicationSettings) -> BatchProcessingService:
    """Return a batch service with mocked validator/generator by default unset."""
    return BatchProcessingService(app_settings)


def test_empty_collection(app_settings: ApplicationSettings) -> None:
    """Empty input should produce zero counts and a non-negative duration."""
    service = BatchProcessingService(app_settings)
    batch = service.process_books([])

    assert batch.total_processed == 0
    assert batch.successful_generations == 0
    assert batch.existing_barcodes_skipped == 0
    assert batch.validation_failures == 0
    assert batch.generation_failures == 0
    assert batch.elapsed_seconds >= 0.0
    assert batch.results == []


def test_successful_processing(app_settings: ApplicationSettings) -> None:
    """Valid books should validate and generate barcodes."""
    book = _valid_book()
    validator = MagicMock()
    validator.validate.return_value = ValidationResult(
        isbn="9780064400558",
        is_valid=True,
        errors=[],
    )
    generator = MagicMock()
    output = app_settings.barcode_output_directory / "9780064400558.png"
    generator.generate_for_book.return_value = BarcodeGenerationResult(
        isbn="9780064400558",
        status=BarcodeStatus.GENERATED,
        output_path=output,
        message="Barcode image created",
        title=book.title,
    )
    service = BatchProcessingService(
        app_settings,
        validator=validator,
        generator=generator,
    )

    batch = service.process_books([book])

    assert batch.total_processed == 1
    assert batch.successful_generations == 1
    assert batch.results[0].status == BookProcessingStatus.GENERATED
    assert batch.results[0].output_path == output
    generator.generate_for_book.assert_called_once_with(book)


def test_mixed_valid_and_invalid_books(app_settings: ApplicationSettings) -> None:
    """Invalid books should fail validation while valid books still generate."""
    valid = _valid_book()
    invalid = _invalid_book()

    def _validate(isbn: str) -> ValidationResult:
        if isbn == invalid.isbn:
            return ValidationResult(
                isbn="123",
                is_valid=False,
                errors=["ISBN-13 must contain exactly 13 digits"],
                error_code=ValidationErrorCode.INVALID_LENGTH,
            )
        return ValidationResult(isbn="9780064400558", is_valid=True, errors=[])

    validator = MagicMock()
    validator.validate.side_effect = _validate
    generator = MagicMock()
    output = app_settings.barcode_output_directory / "9780064400558.png"
    generator.generate_for_book.return_value = BarcodeGenerationResult(
        isbn="9780064400558",
        status=BarcodeStatus.GENERATED,
        output_path=output,
        message="ok",
        title=valid.title,
    )
    service = BatchProcessingService(
        app_settings,
        validator=validator,
        generator=generator,
    )

    batch = service.process_books([invalid, valid])

    assert batch.total_processed == 2
    assert batch.validation_failures == 1
    assert batch.successful_generations == 1
    assert batch.results[0].status == BookProcessingStatus.VALIDATION_FAILED
    assert batch.results[1].status == BookProcessingStatus.GENERATED
    generator.generate_for_book.assert_called_once_with(valid)


def test_existing_barcode_handling(app_settings: ApplicationSettings) -> None:
    """Existing barcode files should be reported as ALREADY_EXISTS skips."""
    book = _valid_book()
    validator = MagicMock()
    validator.validate.return_value = ValidationResult(
        isbn="9780064400558",
        is_valid=True,
        errors=[],
    )
    generator = MagicMock()
    output = app_settings.barcode_output_directory / "9780064400558.png"
    generator.generate_for_book.return_value = BarcodeGenerationResult(
        isbn="9780064400558",
        status=BarcodeStatus.ALREADY_EXISTS,
        output_path=output,
        message="Barcode image already exists",
        title=book.title,
    )
    service = BatchProcessingService(
        app_settings,
        validator=validator,
        generator=generator,
    )

    batch = service.process_books([book])

    assert batch.existing_barcodes_skipped == 1
    assert batch.successful_generations == 0
    assert batch.results[0].status == BookProcessingStatus.ALREADY_EXISTS


def test_generation_failures_and_continuation(
    app_settings: ApplicationSettings,
) -> None:
    """Generation failures must not stop later books from processing."""
    first = _valid_book(title="First")
    second = _valid_book(isbn="9780140328721", title="Second")

    validator = MagicMock()
    validator.validate.side_effect = [
        ValidationResult(isbn="9780064400558", is_valid=True, errors=[]),
        ValidationResult(isbn="9780140328721", is_valid=True, errors=[]),
    ]
    generator = MagicMock()
    generator.generate_for_book.side_effect = [
        BarcodeGenerationError("boom"),
        BarcodeGenerationResult(
            isbn="9780140328721",
            status=BarcodeStatus.GENERATED,
            output_path=app_settings.barcode_output_directory / "9780140328721.png",
            message="ok",
            title=second.title,
        ),
    ]
    service = BatchProcessingService(
        app_settings,
        validator=validator,
        generator=generator,
    )

    batch = service.process_books([first, second])

    assert batch.total_processed == 2
    assert batch.generation_failures == 1
    assert batch.successful_generations == 1
    assert batch.results[0].status == BookProcessingStatus.GENERATION_FAILED
    assert batch.results[1].status == BookProcessingStatus.GENERATED
    assert generator.generate_for_book.call_count == 2


def test_accurate_summary_statistics(app_settings: ApplicationSettings) -> None:
    """Summary counters should match the mix of per-book outcomes."""
    books = [
        _invalid_book(),
        _valid_book(title="New"),
        _valid_book(isbn="9780140328721", title="Exists"),
        _valid_book(isbn="9780060256654", title="Fail"),
    ]
    validator = MagicMock()
    validator.validate.side_effect = [
        ValidationResult(
            isbn="123",
            is_valid=False,
            errors=["bad"],
            error_code=ValidationErrorCode.INVALID_LENGTH,
        ),
        ValidationResult(isbn="9780064400558", is_valid=True, errors=[]),
        ValidationResult(isbn="9780140328721", is_valid=True, errors=[]),
        ValidationResult(isbn="9780060256654", is_valid=True, errors=[]),
    ]
    generator = MagicMock()
    generator.generate_for_book.side_effect = [
        BarcodeGenerationResult(
            isbn="9780064400558",
            status=BarcodeStatus.GENERATED,
            output_path=Path("a.png"),
            message="created",
        ),
        BarcodeGenerationResult(
            isbn="9780140328721",
            status=BarcodeStatus.ALREADY_EXISTS,
            output_path=Path("b.png"),
            message="exists",
        ),
        RuntimeError("disk full"),
    ]
    service = BatchProcessingService(
        app_settings,
        validator=validator,
        generator=generator,
    )

    batch = service.process_books(books)
    summary = batch.to_dict()["summary"]

    assert summary["total_processed"] == 4
    assert summary["successful_generations"] == 1
    assert summary["existing_barcodes_skipped"] == 1
    assert summary["validation_failures"] == 1
    assert summary["generation_failures"] == 1
    assert summary["elapsed_seconds"] >= 0.0


def test_duration_measurement(app_settings: ApplicationSettings) -> None:
    """Elapsed time should be recorded using a monotonic clock."""
    book = _valid_book()
    validator = MagicMock()
    validator.validate.return_value = ValidationResult(
        isbn="9780064400558",
        is_valid=True,
        errors=[],
    )
    generator = MagicMock()

    def _slow_generate(book: Book) -> BarcodeGenerationResult:
        import time

        time.sleep(0.02)
        return BarcodeGenerationResult(
            isbn="9780064400558",
            status=BarcodeStatus.GENERATED,
            output_path=Path("x.png"),
            message="ok",
            title=book.title,
        )

    generator.generate_for_book.side_effect = _slow_generate
    service = BatchProcessingService(
        app_settings,
        validator=validator,
        generator=generator,
    )

    batch = service.process_books([book])
    assert batch.elapsed_seconds >= 0.02


def test_results_preserve_input_order(app_settings: ApplicationSettings) -> None:
    """BookProcessingResult entries must match the input collection order."""
    books = [
        Book(isbn="123", title="First", author="A", copies=1),
        Book(isbn="9780064400558", title="Second", author="A", copies=1),
        Book(isbn="999", title="Third", author="A", copies=1),
        Book(isbn="9780140328721", title="Fourth", author="A", copies=1),
    ]
    validator = MagicMock()
    validator.validate.side_effect = [
        ValidationResult(
            isbn="123",
            is_valid=False,
            errors=["bad"],
            error_code=ValidationErrorCode.INVALID_LENGTH,
        ),
        ValidationResult(isbn="9780064400558", is_valid=True, errors=[]),
        ValidationResult(
            isbn="999",
            is_valid=False,
            errors=["bad"],
            error_code=ValidationErrorCode.INVALID_LENGTH,
        ),
        ValidationResult(isbn="9780140328721", is_valid=True, errors=[]),
    ]
    generator = MagicMock()
    generator.generate_for_book.side_effect = [
        BarcodeGenerationResult(
            isbn="9780064400558",
            status=BarcodeStatus.GENERATED,
            output_path=Path("a.png"),
            message="ok",
            title="Second",
        ),
        BarcodeGenerationResult(
            isbn="9780140328721",
            status=BarcodeStatus.ALREADY_EXISTS,
            output_path=Path("b.png"),
            message="exists",
            title="Fourth",
        ),
    ]
    service = BatchProcessingService(
        app_settings,
        validator=validator,
        generator=generator,
    )

    batch = service.process_books(books)

    assert [result.title for result in batch.results] == [
        "First",
        "Second",
        "Third",
        "Fourth",
    ]
    assert [book.title for book in books] == [result.title for result in batch.results]


def test_books_per_second_derived_metric() -> None:
    """books_per_second should derive from count/elapsed and handle zero time."""
    empty = BatchProcessingResult(results=[], elapsed_seconds=0.0)
    assert empty.books_per_second == 0.0

    results = [
        BookProcessingResult(
            isbn="9780064400558",
            title="A",
            status=BookProcessingStatus.GENERATED,
        ),
        BookProcessingResult(
            isbn="123",
            title="B",
            status=BookProcessingStatus.VALIDATION_FAILED,
        ),
    ]
    batch = BatchProcessingResult(results=results, elapsed_seconds=2.0)
    assert batch.books_per_second == 1.0
    assert batch.to_dict()["summary"]["books_per_second"] == 1.0


def test_cancellation_token_accepted_but_not_enforced(
    app_settings: ApplicationSettings,
) -> None:
    """Cancellation token is accepted for API stability but does not stop the batch."""
    books = [
        _valid_book(title="One"),
        _valid_book(isbn="9780140328721", title="Two"),
    ]
    validator = MagicMock()
    validator.validate.side_effect = [
        ValidationResult(isbn="9780064400558", is_valid=True, errors=[]),
        ValidationResult(isbn="9780140328721", is_valid=True, errors=[]),
    ]
    generator = MagicMock()
    generator.generate_for_book.side_effect = [
        BarcodeGenerationResult(
            isbn="9780064400558",
            status=BarcodeStatus.GENERATED,
            output_path=Path("a.png"),
            message="ok",
            title="One",
        ),
        BarcodeGenerationResult(
            isbn="9780140328721",
            status=BarcodeStatus.GENERATED,
            output_path=Path("b.png"),
            message="ok",
            title="Two",
        ),
    ]
    token = MagicMock()
    token.is_cancellation_requested.return_value = True
    service = BatchProcessingService(
        app_settings,
        validator=validator,
        generator=generator,
        cancellation_token=token,
    )

    batch = service.process_books(books)

    assert batch.total_processed == 2
    token.is_cancellation_requested.assert_not_called()


def test_progress_reporter_invoked(app_settings: ApplicationSettings) -> None:
    """Optional progress reporter should observe start, each book, and completion."""
    books = [_valid_book(), _invalid_book()]
    validator = MagicMock()
    validator.validate.side_effect = [
        ValidationResult(isbn="9780064400558", is_valid=True, errors=[]),
        ValidationResult(
            isbn="123",
            is_valid=False,
            errors=["bad"],
            error_code=ValidationErrorCode.INVALID_LENGTH,
        ),
    ]
    generator = MagicMock()
    generator.generate_for_book.return_value = BarcodeGenerationResult(
        isbn="9780064400558",
        status=BarcodeStatus.GENERATED,
        output_path=Path("a.png"),
        message="ok",
    )
    reporter = MagicMock()
    service = BatchProcessingService(
        app_settings,
        validator=validator,
        generator=generator,
        progress_reporter=reporter,
    )

    batch = service.process_books(books)

    reporter.on_batch_started.assert_called_once_with(2)
    assert reporter.on_book_processed.call_count == 2
    reporter.on_book_processed.assert_any_call(1, 2, batch.results[0])
    reporter.on_book_processed.assert_any_call(2, 2, batch.results[1])
    reporter.on_batch_completed.assert_called_once_with(2)


def test_real_end_to_end_batch(app_settings: ApplicationSettings) -> None:
    """Integration-style run with real validator and generator."""
    books = [
        _valid_book(),
        _invalid_book(),
        _valid_book(isbn="978-0-06-440055-8", title="Dup"),
    ]
    # Pre-create the barcode so the second valid ISBN is skipped.
    service = BatchProcessingService(app_settings)
    first = service.process_books([books[0]])
    assert first.successful_generations == 1

    batch = service.process_books(books)
    assert batch.total_processed == 3
    assert batch.successful_generations == 0
    assert batch.existing_barcodes_skipped == 2
    assert batch.validation_failures == 1
    assert batch.generation_failures == 0
    assert all(
        r.output_path is not None and r.output_path.is_file()
        for r in batch.results
        if r.status == BookProcessingStatus.ALREADY_EXISTS
    )
