"""Library-agnostic contract for writing ISBN updates into an inventory copy."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol


class InventoryWorkbookUpdater(Protocol):
    """Copy an inventory workbook and update ISBN cells only.

    Implementations must never overwrite ``source_path``.
    """

    def write_isbn_updates(
        self,
        *,
        source_path: Path,
        destination_path: Path,
        sheet_name: str,
        header_row: int,
        isbn_column_name: str,
        updates: Sequence[tuple[int, str]],
    ) -> Path:
        """Load ``source_path``, apply ISBN updates, save to ``destination_path``.

        Args:
            source_path: Original teacher inventory (read only).
            destination_path: New workbook path (must not be ``source_path``).
            sheet_name: Worksheet containing the book table.
            header_row: 1-based header row index.
            isbn_column_name: Header text for the ISBN column.
            updates: ``(row_number, isbn)`` pairs (1-based Excel rows).

        Returns:
            The path written (``destination_path``).

        Raises:
            ValueError: When ``destination_path`` equals ``source_path``.
            FileNotFoundError / OSError: When the source cannot be read or
                destination cannot be written.
            KeyError: When the sheet or ISBN column cannot be resolved.
        """
        ...
