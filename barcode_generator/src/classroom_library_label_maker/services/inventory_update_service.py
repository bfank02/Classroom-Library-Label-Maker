"""Orchestrate writing an updated inventory workbook after ISBN review.

Depends on :class:`InventoryWorkbookUpdater` for Excel I/O. Does not import
openpyxl or Qt.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from classroom_library_label_maker.constants import (
    MISSING_ISBN_PLACEHOLDER,
    UPDATED_INVENTORY_FILE_NAME,
)
from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.models import (
    ApplicationSettings,
    Book,
    ReviewSessionResult,
)
from classroom_library_label_maker.services.book_review_service import (
    ReviewSession,
    books_with_review_applied,
)
from classroom_library_label_maker.utils.file_utils import unique_path
from classroom_library_label_maker.workbooks import (
    openpyxl_inventory_workbook_updater as openpyxl_inventory,
)
from classroom_library_label_maker.workbooks.inventory_workbook_updater import (
    InventoryWorkbookUpdater,
)

_logger = get_logger("inventory_update_service")


class InventoryUpdateService:
    """Build ISBN cell updates and write a non-destructive inventory copy."""

    def __init__(
        self,
        *,
        updater: InventoryWorkbookUpdater | None = None,
    ) -> None:
        self._updater: InventoryWorkbookUpdater = (
            updater or openpyxl_inventory.OpenPyxlInventoryWorkbookUpdater()
        )

    def write_updated_inventory(
        self,
        *,
        source_path: Path,
        settings: ApplicationSettings,
        books: Sequence[Book],
        source_rows: Sequence[int],
        session: ReviewSession,
        review_result: ReviewSessionResult,
        destination_path: Path | None = None,
    ) -> Path:
        """Merge review decisions into books and write an updated workbook copy.

        Automatically enriched ISBNs already present on ``books`` are included.
        Skipped / unresolved review rows that still use the missing-ISBN
        placeholder are left unchanged in the workbook.
        """
        if len(books) != len(source_rows):
            raise ValueError(
                "books and source_rows must have the same length "
                f"(got {len(books)} books and {len(source_rows)} rows)"
            )
        source = Path(source_path)
        destination = (
            Path(destination_path)
            if destination_path is not None
            else default_updated_inventory_path(source)
        )
        merged = books_with_review_applied(books, session, review_result)
        updates = isbn_cell_updates(merged, source_rows)
        written = self._updater.write_isbn_updates(
            source_path=source,
            destination_path=destination,
            sheet_name=settings.workbook_sheet_name,
            header_row=settings.workbook_header_row,
            isbn_column_name=settings.workbook_column_isbn,
            updates=updates,
        )
        _logger.info(
            "Inventory update complete: %s (%s ISBN cell(s))",
            written,
            len(updates),
        )
        return written


def default_updated_inventory_path(source_path: Path) -> Path:
    """Return a unique path beside ``source_path`` for the updated inventory."""
    proposed = Path(source_path).parent / UPDATED_INVENTORY_FILE_NAME
    return unique_path(proposed)


def isbn_cell_updates(
    books: Sequence[Book],
    source_rows: Sequence[int],
) -> tuple[tuple[int, str], ...]:
    """Build ``(row, isbn)`` pairs for books with a real ISBN to write."""
    updates: list[tuple[int, str]] = []
    for book, row in zip(books, source_rows, strict=True):
        isbn = (book.isbn or "").strip()
        if not isbn:
            continue
        if isbn.casefold() == MISSING_ISBN_PLACEHOLDER.casefold():
            continue
        updates.append((int(row), isbn))
    return tuple(updates)
