"""Library-agnostic workbook writing contracts.

Used by :class:`~classroom_library_label_maker.services.workbook_generation_service.WorkbookGenerationService`
to create, populate (via :class:`LabelSheetTarget`), and save label workbooks
without depending on openpyxl in the service layer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from classroom_library_label_maker.workbooks.label_sheet_target import LabelSheetTarget


class WorkbookWriter(Protocol):
    """Protocol for creating and saving label workbooks without vendor types."""

    def create_workbook(self) -> None:
        """Create a new empty workbook ready for label pages."""
        ...

    def get_label_sheet_target(self) -> LabelSheetTarget:
        """Return the :class:`LabelSheetTarget` used by layout.

        Raises:
            RuntimeError: When :meth:`create_workbook` has not been called.
        """
        ...

    def save(self, path: Path) -> Path:
        """Persist the workbook to ``path`` and return the resolved path.

        Args:
            path: Destination ``.xlsx`` path.

        Returns:
            The path written.
        """
        ...

    def close(self) -> None:
        """Release workbook resources (safe if nothing was created)."""
        ...
