"""Excel import service — map workbook rows to :class:`Book` models.

This service reads tabular data through a :class:`WorkbookReader` and produces
:class:`ImportResult`. It does not validate ISBNs, generate barcodes, run
batch processing, modify workbooks, or display UI.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import time

from classroom_library_label_maker.exceptions import (
    ConfigurationError,
    FileSystemError,
    InvalidWorkbookError,
)
from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.models import (
    ApplicationSettings,
    Book,
    ImportResult,
    ImportWarning,
)
from classroom_library_label_maker.workbooks.openpyxl_workbook_reader import (
    OpenPyxlWorkbookReader,
)
from classroom_library_label_maker.workbooks.workbook_reader import WorkbookReader

_logger = get_logger("excel_import_service")


class ExcelImportService:
    """Import books from an Excel workbook via :class:`WorkbookReader`.

    Column names, worksheet name, and workbook path come from
    :class:`ApplicationSettings` (or an explicit path override).
    """

    def __init__(
        self,
        settings: ApplicationSettings,
        *,
        reader: WorkbookReader | None = None,
    ) -> None:
        """Initialize the import service.

        Args:
            settings: Application settings (workbook path, sheet, columns).
            reader: Optional workbook reader (defaults to
                :class:`OpenPyxlWorkbookReader`).
        """
        self._settings = settings
        self._reader: WorkbookReader = reader or OpenPyxlWorkbookReader()

    def import_books(self, workbook_path: Path | None = None) -> ImportResult:
        """Import books from the configured (or overridden) workbook.

        Args:
            workbook_path: Optional path override; otherwise
                ``settings.workbook_path`` is used.

        Returns:
            :class:`ImportResult` with books, statistics, and warnings.

        Raises:
            ConfigurationError: When the workbook path or column config is invalid.
            FileSystemError: When the workbook file is missing or unreadable.
            InvalidWorkbookError: When the workbook/sheet/schema is invalid.
        """
        path = Path(workbook_path) if workbook_path is not None else None
        if path is None:
            if self._settings.workbook_path is None:
                raise ConfigurationError(
                    "workbook_path is required for Excel import "
                    "(set ApplicationSettings.workbook_path or pass workbook_path)"
                )
            path = Path(self._settings.workbook_path)

        sheet_name = self._settings.workbook_sheet_name
        header_row = self._settings.workbook_header_row
        started = time.perf_counter()

        self._open_workbook(path)
        try:
            _logger.info("Workbook opened: %s", path)
            self._ensure_worksheet(sheet_name)
            _logger.info("Worksheet selected: %s", sheet_name)

            rows = list(self._reader.iter_rows(sheet_name, min_row=header_row))
            if not rows:
                raise InvalidWorkbookError(
                    f"Worksheet {sheet_name!r} has no rows (header_row={header_row})"
                )

            column_index = self._resolve_columns(rows[0], sheet_name)
            result = self._import_data_rows(
                data_rows=rows[1:],
                first_data_row=header_row + 1,
                column_index=column_index,
            )
            result.workbook_path = path
            result.worksheet_name = sheet_name
            result.elapsed_seconds = time.perf_counter() - started
        finally:
            self._reader.close()

        _logger.info(
            "Import completed: path=%s sheet=%s imported=%s skipped=%s "
            "warnings=%s elapsed=%.3fs",
            path,
            sheet_name,
            result.imported_rows,
            result.skipped_rows,
            len(result.warnings),
            result.elapsed_seconds,
        )
        return result

    def _open_workbook(self, path: Path) -> None:
        if not path.is_file():
            _logger.error("Workbook missing: %s", path)
            raise FileSystemError(f"Workbook not found: {path}")
        try:
            self._reader.open(path)
        except FileNotFoundError as exc:
            raise FileSystemError(f"Workbook not found: {path}", cause=exc) from exc
        except OSError as exc:
            raise FileSystemError(
                f"Unable to read workbook: {path}",
                cause=exc,
            ) from exc
        except ValueError as exc:
            raise InvalidWorkbookError(
                f"Invalid workbook: {path}",
                cause=exc,
            ) from exc

    def _ensure_worksheet(self, sheet_name: str) -> None:
        names = list(self._reader.sheet_names())
        if sheet_name not in names:
            raise InvalidWorkbookError(
                f"Worksheet {sheet_name!r} not found in workbook "
                f"(available: {', '.join(names) or 'none'})"
            )

    def _resolve_columns(
        self,
        header_cells: Sequence[str | None],
        sheet_name: str,
    ) -> dict[str, int]:
        """Map configured column names to 0-based indices."""
        normalized: dict[str, int] = {}
        for index, cell in enumerate(header_cells):
            if cell is None:
                continue
            key = cell.strip().casefold()
            if key and key not in normalized:
                normalized[key] = index

        required = {
            "isbn": self._settings.workbook_column_isbn,
            "title": self._settings.workbook_column_title,
            "author": self._settings.workbook_column_author,
            "copies": self._settings.workbook_column_copies,
        }
        resolved: dict[str, int] = {}
        missing: list[str] = []
        for field_name, header_name in required.items():
            index = normalized.get(header_name.strip().casefold())
            if index is None:
                missing.append(header_name)
            else:
                resolved[field_name] = index

        if missing:
            raise InvalidWorkbookError(
                f"Worksheet {sheet_name!r} is missing required column(s): "
                + ", ".join(missing)
            )
        return resolved

    def _import_data_rows(
        self,
        *,
        data_rows: Sequence[Sequence[str | None]],
        first_data_row: int,
        column_index: Mapping[str, int],
    ) -> ImportResult:
        books: list[Book] = []
        source_rows: list[int] = []
        warnings: list[ImportWarning] = []
        imported = 0
        skipped = 0

        for offset, cells in enumerate(data_rows):
            row_number = first_data_row + offset
            if self._is_blank_row(cells):
                skipped += 1
                continue

            book, warning = self._map_row(cells, column_index, row_number)
            if warning is not None:
                warnings.append(warning)
                _logger.warning("%s", warning.message)
                skipped += 1
                continue

            assert book is not None
            books.append(book)
            source_rows.append(row_number)
            imported += 1

        total_rows = len(data_rows)
        _logger.info(
            "Rows imported=%s skipped=%s total_data_rows=%s warnings=%s",
            imported,
            skipped,
            total_rows,
            len(warnings),
        )
        return ImportResult(
            books=books,
            source_rows=source_rows,
            total_rows=total_rows,
            imported_rows=imported,
            skipped_rows=skipped,
            warnings=warnings,
        )

    def _map_row(
        self,
        cells: Sequence[str | None],
        column_index: Mapping[str, int],
        row_number: int,
    ) -> tuple[Book | None, ImportWarning | None]:
        isbn = self._cell_at(cells, column_index["isbn"])
        title = self._cell_at(cells, column_index["title"])
        author = self._cell_at(cells, column_index["author"])
        copies_raw = self._cell_at(cells, column_index["copies"])

        if not isbn:
            return None, ImportWarning(
                message=f"Row {row_number}: missing ISBN",
                row_number=row_number,
                code="missing_isbn",
            )
        if not title:
            return None, ImportWarning(
                message=f"Row {row_number}: missing Title",
                row_number=row_number,
                code="missing_title",
            )
        if not author:
            return None, ImportWarning(
                message=f"Row {row_number}: missing Author",
                row_number=row_number,
                code="missing_author",
            )

        try:
            copies = self._parse_copies(copies_raw)
        except ValueError as exc:
            return None, ImportWarning(
                message=f"Row {row_number}: {exc}",
                row_number=row_number,
                code="invalid_copies",
            )

        try:
            book = Book(isbn=isbn, title=title, author=author, copies=copies)
        except ValueError as exc:
            return None, ImportWarning(
                message=f"Row {row_number}: {exc}",
                row_number=row_number,
                code="invalid_book",
            )
        return book, None

    @staticmethod
    def _parse_copies(raw: str | None) -> int:
        if raw is None or not raw.strip():
            return 1
        text = raw.strip()
        try:
            # Allow "2.0" from Excel numeric cells converted to strings.
            value = int(float(text)) if "." in text else int(text)
        except ValueError as exc:
            raise ValueError(f"invalid Copies value {raw!r}") from exc
        if value < 1:
            raise ValueError(f"Copies must be >= 1 (got {value})")
        return value

    @staticmethod
    def _cell_at(cells: Sequence[str | None], index: int) -> str | None:
        if index < 0 or index >= len(cells):
            return None
        return cells[index]

    @staticmethod
    def _is_blank_row(cells: Sequence[str | None]) -> bool:
        return all(cell is None or not str(cell).strip() for cell in cells)
