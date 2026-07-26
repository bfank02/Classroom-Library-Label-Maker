"""Tests for the workbook generation (end-to-end orchestration) service."""

from __future__ import annotations

from pathlib import Path

import pytest

from classroom_library_label_maker.exceptions import (
    ConfigurationError,
    FileSystemError,
    InvalidWorkbookError,
    WorkbookGenerationError,
)
from classroom_library_label_maker.models import (
    ApplicationSettings,
    BatchProcessingResult,
    Book,
    BookProcessingResult,
    BookProcessingStatus,
    ImportResult,
    ImportWarning,
    WorkbookGenerationResult,
)
from classroom_library_label_maker.services.workbook_generation_service import (
    WorkbookGenerationService,
)
from classroom_library_label_maker.workbooks.in_memory_workbook_writer import (
    InMemoryWorkbookWriter,
)
from classroom_library_label_maker.workbooks.label_sheet_target import LabelSheetTarget

WORKBOOKS = Path(__file__).resolve().parent / "assets" / "workbooks"


def _book(isbn: str, title: str = "Title", author: str = "Author") -> Book:
    return Book(isbn=isbn, title=title, author=author, copies=1)


class _StubImporter:
    def __init__(self, result: ImportResult) -> None:
        self.result = result
        self.calls: list[Path | None] = []

    def import_books(self, workbook_path: Path | None = None) -> ImportResult:
        self.calls.append(workbook_path)
        return self.result


class _StubBatch:
    def __init__(self, result: BatchProcessingResult) -> None:
        self.result = result
        self.books: list[Book] | None = None

    def process_books(self, books: list[Book]) -> BatchProcessingResult:
        self.books = list(books)
        return self.result


class _FailingWriter(InMemoryWorkbookWriter):
    def save(self, path: Path) -> Path:
        raise OSError("disk full")


class _RecordingWriter(InMemoryWorkbookWriter):
    """Capture page numbers at save time (target is cleared on close)."""

    def __init__(self, *, write_marker: bool = False) -> None:
        super().__init__(write_marker=write_marker)
        self.pages_at_save: list[int] = []

    def save(self, path: Path) -> Path:
        if self._target is not None:
            self.pages_at_save = list(self._target.pages)
        return super().save(path)


@pytest.fixture
def gen_settings(app_settings: ApplicationSettings) -> ApplicationSettings:
    """Settings pointed at the valid sample workbook."""
    app_settings.workbook_path = WORKBOOKS / "valid_books.xlsx"
    app_settings.workbook_sheet_name = "Books"
    return app_settings


def test_successful_generation_end_to_end(
    gen_settings: ApplicationSettings,
    tmp_path: Path,
) -> None:
    """Inventory workbook should produce a saved label workbook on disk."""
    output = tmp_path / "out" / "labels.xlsx"
    result = WorkbookGenerationService(gen_settings).generate(output_path=output)

    assert isinstance(result, WorkbookGenerationResult)
    assert result.books_imported == 2
    assert result.books_processed == 2
    assert result.labels_created == 3
    assert result.pages_created == 1
    assert result.barcodes_generated == 2
    assert result.barcodes_reused == 0
    assert result.output_path == output.resolve()
    assert output.is_file()
    assert output.stat().st_size > 0
    assert result.elapsed_seconds >= 0.0


def test_empty_workbook_generates_empty_labels(
    gen_settings: ApplicationSettings,
    tmp_path: Path,
) -> None:
    """Header-only inventory should save a workbook with zero labels."""
    writer = InMemoryWorkbookWriter(write_marker=True)
    output = tmp_path / "empty_labels.xlsx"
    service = WorkbookGenerationService(gen_settings, writer=writer)

    result = service.generate(
        workbook_path=WORKBOOKS / "empty_books.xlsx",
        output_path=output,
    )

    assert result.books_imported == 0
    assert result.books_processed == 0
    assert result.labels_created == 0
    assert result.pages_created == 0
    assert result.barcodes_generated == 0
    assert writer.created is True
    assert writer.save_calls == 1
    assert writer.closed is True


def test_import_failure_propagates(
    gen_settings: ApplicationSettings,
    tmp_path: Path,
) -> None:
    """Missing inventory workbooks should raise FileSystemError."""
    with pytest.raises(FileSystemError, match="not found"):
        WorkbookGenerationService(gen_settings).generate(
            workbook_path=WORKBOOKS / "does_not_exist.xlsx",
            output_path=tmp_path / "out.xlsx",
        )


def test_invalid_workbook_propagates(
    gen_settings: ApplicationSettings,
    tmp_path: Path,
) -> None:
    """Corrupt inventory workbooks should raise InvalidWorkbookError."""
    with pytest.raises(InvalidWorkbookError, match="Invalid workbook"):
        WorkbookGenerationService(gen_settings).generate(
            workbook_path=WORKBOOKS / "not_a_workbook.xlsx",
            output_path=tmp_path / "out.xlsx",
        )


def test_missing_workbook_path_configuration(
    app_settings: ApplicationSettings,
    tmp_path: Path,
) -> None:
    """Missing workbook_path should raise ConfigurationError."""
    app_settings.workbook_path = None
    with pytest.raises(ConfigurationError, match="workbook_path is required"):
        WorkbookGenerationService(app_settings).generate(
            output_path=tmp_path / "out.xlsx"
        )


def test_save_failure_maps_to_filesystem_error(
    gen_settings: ApplicationSettings,
    tmp_path: Path,
) -> None:
    """OSError from the writer should become FileSystemError."""
    books = [_book("9780064400558", title="A"), _book("9780060256654", title="B")]
    importer = _StubImporter(
        ImportResult(books=books, imported_rows=2, total_rows=2, source_rows=[2, 3])
    )
    batch = _StubBatch(
        BatchProcessingResult(
            results=[
                BookProcessingResult(
                    isbn="9780064400558",
                    title="A",
                    status=BookProcessingStatus.GENERATED,
                    output_path=tmp_path / "9780064400558.png",
                ),
                BookProcessingResult(
                    isbn="9780060256654",
                    title="B",
                    status=BookProcessingStatus.GENERATED,
                    output_path=tmp_path / "9780060256654.png",
                ),
            ]
        )
    )
    service = WorkbookGenerationService(
        gen_settings,
        importer=importer,  # type: ignore[arg-type]
        batch_processor=batch,  # type: ignore[arg-type]
        writer=_FailingWriter(),
    )
    with pytest.raises(FileSystemError, match="Failed to save label workbook"):
        service.generate(output_path=tmp_path / "out.xlsx")


def test_multiple_pages(
    gen_settings: ApplicationSettings,
    tmp_path: Path,
) -> None:
    """More books than labels_per_page should create multiple pages."""
    books = [
        _book(f"97800000000{i:02d}"[:13].ljust(13, "0"), title=f"Book {i}")
        for i in range(31)
    ]
    importer = _StubImporter(
        ImportResult(
            books=books,
            imported_rows=31,
            total_rows=31,
            source_rows=list(range(2, 33)),
        )
    )
    batch_results = [
        BookProcessingResult(
            isbn=book.isbn,
            title=book.title,
            status=BookProcessingStatus.ALREADY_EXISTS,
            output_path=tmp_path / f"{book.isbn}.png",
        )
        for book in books
    ]
    writer = _RecordingWriter(write_marker=True)
    service = WorkbookGenerationService(
        gen_settings,
        importer=importer,  # type: ignore[arg-type]
        batch_processor=_StubBatch(BatchProcessingResult(results=batch_results)),  # type: ignore[arg-type]
        writer=writer,
    )

    result = service.generate(output_path=tmp_path / "multi.xlsx")

    assert result.labels_created == 31
    assert result.pages_created == 2
    assert writer.pages_at_save == [1, 2]


def test_existing_barcode_reuse(
    gen_settings: ApplicationSettings,
    tmp_path: Path,
) -> None:
    """Pre-existing PNG files should count as barcodes_reused."""
    # Generate once
    first_out = tmp_path / "first.xlsx"
    WorkbookGenerationService(gen_settings).generate(output_path=first_out)

    writer = InMemoryWorkbookWriter(write_marker=True)
    second = WorkbookGenerationService(gen_settings, writer=writer).generate(
        output_path=tmp_path / "second.xlsx"
    )

    assert second.barcodes_generated == 0
    assert second.barcodes_reused == 2
    assert second.labels_created == 3


def test_generated_barcodes_counted(
    gen_settings: ApplicationSettings,
    tmp_path: Path,
) -> None:
    """First run should report barcodes_generated for new PNGs."""
    result = WorkbookGenerationService(
        gen_settings,
        writer=InMemoryWorkbookWriter(write_marker=True),
    ).generate(output_path=tmp_path / "labels.xlsx")

    assert result.barcodes_generated == 2
    assert result.barcodes_reused == 0
    pngs = list(Path(gen_settings.barcode_output_directory).glob("*.png"))
    assert len(pngs) == 2


def test_result_statistics(
    gen_settings: ApplicationSettings,
    tmp_path: Path,
) -> None:
    """WorkbookGenerationResult.to_dict should expose summary statistics."""
    result = WorkbookGenerationService(
        gen_settings,
        writer=InMemoryWorkbookWriter(write_marker=True),
    ).generate(output_path=tmp_path / "stats.xlsx")

    summary = result.to_dict()["summary"]
    assert summary["books_imported"] == 2
    assert summary["books_processed"] == 2
    assert summary["labels_created"] == 3
    assert summary["pages_created"] == 1
    assert summary["barcodes_generated"] == 2
    assert summary["output_path"] is not None
    assert "warning_count" in summary
    assert summary["requires_review"] is False
    assert summary["completion_state"] == "success"


def test_writer_interaction(
    gen_settings: ApplicationSettings,
    tmp_path: Path,
) -> None:
    """Writer create → layout target → save → close should be invoked."""
    writer = InMemoryWorkbookWriter(write_marker=True)
    output = tmp_path / "writer.xlsx"
    WorkbookGenerationService(gen_settings, writer=writer).generate(output_path=output)

    assert writer.created is True
    assert writer.save_calls == 1
    assert writer.saved_path == output
    assert writer.closed is True


def test_import_and_batch_warnings_collected(
    gen_settings: ApplicationSettings,
    tmp_path: Path,
) -> None:
    """Import and batch failures should appear in result warnings."""
    books = [
        _book("9780064400558", title="Good"),
        _book("123", title="Bad"),
    ]
    importer = _StubImporter(
        ImportResult(
            books=books,
            imported_rows=2,
            total_rows=2,
            source_rows=[2, 3],
            warnings=(
                ImportWarning(message="odd row", row_number=4, code="odd"),
            ),
        )
    )
    batch = _StubBatch(
        BatchProcessingResult(
            results=[
                BookProcessingResult(
                    isbn="9780064400558",
                    title="Good",
                    status=BookProcessingStatus.GENERATED,
                    output_path=tmp_path / "9780064400558.png",
                ),
                BookProcessingResult(
                    isbn="123",
                    title="Bad",
                    status=BookProcessingStatus.VALIDATION_FAILED,
                    message="invalid isbn",
                ),
            ]
        )
    )
    result = WorkbookGenerationService(
        gen_settings,
        importer=importer,  # type: ignore[arg-type]
        batch_processor=batch,  # type: ignore[arg-type]
        writer=InMemoryWorkbookWriter(write_marker=True),
    ).generate(output_path=tmp_path / "warn.xlsx")

    codes = {w.code for w in result.warnings}
    assert "odd" in codes
    assert "validation_failed" in codes
    assert "missing_barcode" in codes  # bad book has no barcode path


def test_unexpected_writer_failure_maps_to_workbook_generation_error(
    gen_settings: ApplicationSettings,
    tmp_path: Path,
) -> None:
    """Unexpected writer failures should become WorkbookGenerationError."""

    class BoomWriter:
        def create_workbook(self) -> None:
            raise RuntimeError("boom")

        def get_label_sheet_target(self) -> LabelSheetTarget:
            raise RuntimeError("unused")

        def save(self, path: Path) -> Path:
            return path

        def close(self) -> None:
            return None

    importer = _StubImporter(ImportResult(books=[], imported_rows=0, total_rows=0))
    batch = _StubBatch(BatchProcessingResult(results=[]))
    service = WorkbookGenerationService(
        gen_settings,
        importer=importer,  # type: ignore[arg-type]
        batch_processor=batch,  # type: ignore[arg-type]
        writer=BoomWriter(),  # type: ignore[arg-type]
    )
    with pytest.raises(WorkbookGenerationError, match="Workbook generation failed"):
        service.generate(output_path=tmp_path / "out.xlsx")


def test_default_output_path_under_project_output(
    gen_settings: ApplicationSettings,
) -> None:
    """When output_path is omitted, save under project_root/output/."""
    writer = InMemoryWorkbookWriter(write_marker=True)
    result = WorkbookGenerationService(gen_settings, writer=writer).generate()
    expected = Path(gen_settings.project_root) / "output" / "library_labels.xlsx"
    assert result.output_path == expected
    assert writer.saved_path == expected
