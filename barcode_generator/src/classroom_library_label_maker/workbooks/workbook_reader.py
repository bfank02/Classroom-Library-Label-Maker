"""Library-agnostic workbook reading contracts.

This module defines the public workbook abstraction used by future Excel
import services. Implementations must not leak third-party library types
(such as openpyxl workbooks or cells) through this interface.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Protocol


class WorkbookReader(Protocol):
    """Protocol for reading tabular workbook data without vendor types.

    Callers (future Excel import services) depend only on this contract so
    Excel backends can be swapped (openpyxl, CSV, Google Sheets, etc.)
    without changing import orchestration or domain mapping.
    """

    def open(self, path: Path) -> None:
        """Open a workbook at ``path`` for subsequent reads.

        Args:
            path: Filesystem path to the workbook file.

        Raises:
            NotImplementedError: Until a concrete reader is implemented.
            FileNotFoundError: When ``path`` does not exist (future).
            OSError: When the file cannot be opened (future).
            ValueError: When the file is not a supported workbook (future).
        """
        ...

    def close(self) -> None:
        """Release resources associated with the open workbook.

        Safe to call when no workbook is open (future implementations should
        treat this as a no-op).
        """
        ...

    def sheet_names(self) -> Sequence[str]:
        """Return the sheet names in workbook order.

        Returns:
            A sequence of sheet name strings.

        Raises:
            NotImplementedError: Until a concrete reader is implemented.
            RuntimeError: When no workbook is open (future).
        """
        ...

    def iter_rows(
        self,
        sheet_name: str,
        *,
        min_row: int = 1,
    ) -> Iterator[tuple[str | None, ...]]:
        """Iterate sheet rows as plain string cells (no vendor cell types).

        Empty cells are represented as ``None``. Numeric or date cell values
        are converted to strings by concrete readers when implemented.

        Args:
            sheet_name: Target sheet name (must exist in :meth:`sheet_names`).
            min_row: 1-based first row to yield (inclusive).

        Yields:
            Tuples of ``str | None`` cell values in column order.

        Raises:
            NotImplementedError: Until a concrete reader is implemented.
            KeyError: When ``sheet_name`` is missing (future).
            RuntimeError: When no workbook is open (future).
        """
        ...
