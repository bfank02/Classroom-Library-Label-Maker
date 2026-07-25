"""Tests for the Excel import engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from classroom_library_label_maker.exceptions import (
    ConfigurationError,
    FileSystemError,
    InvalidWorkbookError,
)
from classroom_library_label_maker.models import ApplicationSettings
from classroom_library_label_maker.services.excel_import_service import (
    ExcelImportService,
)

WORKBOOKS = Path(__file__).resolve().parent / "assets" / "workbooks"


@pytest.fixture
def import_settings(app_settings: ApplicationSettings) -> ApplicationSettings:
    """Settings pointed at the valid sample workbook."""
    app_settings.workbook_path = WORKBOOKS / "valid_books.xlsx"
    app_settings.workbook_sheet_name = "Books"
    return app_settings


def test_valid_workbook(import_settings: ApplicationSettings) -> None:
    """A well-formed workbook should import all data rows."""
    result = ExcelImportService(import_settings).import_books()

    assert result.imported_rows == 2
    assert result.skipped_rows == 0
    assert result.total_rows == 2
    assert len(result.books) == 2
    assert result.source_rows == [2, 3]
    assert result.books[0].isbn == "9780064400558"
    assert result.books[0].title == "Charlotte's Web"
    assert result.books[0].author == "E. B. White"
    assert result.books[0].copies == 1
    assert result.books[1].copies == 2
    assert result.warnings == []
    assert result.elapsed_seconds >= 0.0


def test_empty_workbook(import_settings: ApplicationSettings) -> None:
    """Header-only worksheets should import zero books."""
    result = ExcelImportService(import_settings).import_books(
        WORKBOOKS / "empty_books.xlsx"
    )

    assert result.total_rows == 0
    assert result.imported_rows == 0
    assert result.skipped_rows == 0
    assert result.books == []


def test_blank_rows_are_skipped(import_settings: ApplicationSettings) -> None:
    """Completely blank rows should be skipped without warnings."""
    result = ExcelImportService(import_settings).import_books(
        WORKBOOKS / "blank_rows.xlsx"
    )

    assert result.imported_rows == 2
    assert result.skipped_rows == 2
    assert result.total_rows == 4
    assert result.source_rows == [2, 5]
    assert result.warnings == []


def test_missing_optional_copies_defaults_to_one(
    import_settings: ApplicationSettings,
) -> None:
    """Blank Copies should default to 1."""
    result = ExcelImportService(import_settings).import_books(
        WORKBOOKS / "missing_optional_copies.xlsx"
    )

    assert result.imported_rows == 1
    assert result.books[0].copies == 1
    assert result.warnings == []


def test_missing_workbook(import_settings: ApplicationSettings) -> None:
    """Missing workbook files should raise FileSystemError."""
    with pytest.raises(FileSystemError, match="not found"):
        ExcelImportService(import_settings).import_books(
            WORKBOOKS / "does_not_exist.xlsx"
        )


def test_missing_worksheet(import_settings: ApplicationSettings) -> None:
    """Missing worksheet names should raise InvalidWorkbookError."""
    with pytest.raises(InvalidWorkbookError, match="Worksheet 'Books' not found"):
        ExcelImportService(import_settings).import_books(WORKBOOKS / "wrong_sheet.xlsx")


def test_invalid_workbook(import_settings: ApplicationSettings) -> None:
    """Corrupt workbook files should raise InvalidWorkbookError."""
    with pytest.raises(InvalidWorkbookError, match="Invalid workbook"):
        ExcelImportService(import_settings).import_books(
            WORKBOOKS / "not_a_workbook.xlsx"
        )


def test_missing_required_columns(import_settings: ApplicationSettings) -> None:
    """Missing configured header columns should raise InvalidWorkbookError."""
    with pytest.raises(InvalidWorkbookError, match="missing required column"):
        ExcelImportService(import_settings).import_books(
            WORKBOOKS / "missing_columns.xlsx"
        )


def test_row_mapping_preserves_fields(import_settings: ApplicationSettings) -> None:
    """Mapped books should preserve ISBN/title/author/copies and source rows."""
    result = ExcelImportService(import_settings).import_books()
    book = result.books[1]
    assert book.isbn == "9780060256654"
    assert book.title == "The Giving Tree"
    assert book.author == "Shel Silverstein"
    assert book.copies == 2
    assert result.source_rows[1] == 3


def test_import_statistics_and_warnings(
    import_settings: ApplicationSettings,
) -> None:
    """Malformed rows should warn, skip, and continue importing valid rows."""
    result = ExcelImportService(import_settings).import_books(
        WORKBOOKS / "malformed_rows.xlsx"
    )

    assert result.imported_rows == 1
    assert result.skipped_rows == 5
    assert result.total_rows == 6
    assert len(result.warnings) == 5
    assert {warning.code for warning in result.warnings} == {
        "missing_isbn",
        "missing_title",
        "missing_author",
        "invalid_copies",
    }
    assert all(warning.row_number is not None for warning in result.warnings)
    assert result.books[0].title == "Charlotte's Web"
    summary = result.to_dict()["summary"]
    assert summary["imported_rows"] == 1
    assert summary["skipped_rows"] == 5
    assert summary["warning_count"] == 5


def test_configuration_requires_workbook_path(
    app_settings: ApplicationSettings,
) -> None:
    """Import without a configured path should raise ConfigurationError."""
    app_settings.workbook_path = None
    with pytest.raises(ConfigurationError, match="workbook_path"):
        ExcelImportService(app_settings).import_books()


def test_custom_column_mapping(import_settings: ApplicationSettings) -> None:
    """Configured column header names should drive mapping."""
    # valid_books uses ISBN/Title/Author/Copies — remap to same names explicitly.
    import_settings.workbook_column_isbn = "isbn"
    import_settings.workbook_column_title = "TITLE"
    import_settings.workbook_column_author = "Author"
    import_settings.workbook_column_copies = "Copies"
    result = ExcelImportService(import_settings).import_books()
    assert result.imported_rows == 2
