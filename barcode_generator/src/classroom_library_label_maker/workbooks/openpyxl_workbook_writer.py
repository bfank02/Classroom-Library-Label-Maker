"""openpyxl-backed :class:`WorkbookWriter` (create / layout target / save).

All openpyxl interaction for output workbooks stays in this module. Layout
still goes through :class:`OpenPyxlLabelSheetTarget` / :class:`LabelSheetTarget`.
"""

from __future__ import annotations

from pathlib import Path

from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.utils.file_utils import ensure_directory
from classroom_library_label_maker.workbooks.label_sheet_target import LabelSheetTarget
from classroom_library_label_maker.workbooks.openpyxl_label_sheet_target import (
    OpenPyxlLabelSheetTarget,
)

_logger = get_logger("workbooks.openpyxl_workbook_writer")


class OpenPyxlWorkbookWriter:
    """Create, expose a label sheet target, and save openpyxl workbooks."""

    def __init__(self) -> None:
        """Initialize with no open workbook."""
        self._target: OpenPyxlLabelSheetTarget | None = None

    def create_workbook(self) -> None:
        """Create a new empty workbook via :class:`OpenPyxlLabelSheetTarget`."""
        self.close()
        self._target = OpenPyxlLabelSheetTarget()
        _logger.debug("Created openpyxl workbook for label output")

    def get_label_sheet_target(self) -> LabelSheetTarget:
        """Return the layout target for the current workbook."""
        if self._target is None:
            raise RuntimeError("create_workbook must be called before get_label_sheet_target")
        return self._target

    def save(self, path: Path) -> Path:
        """Save the current workbook to ``path``.

        Args:
            path: Destination ``.xlsx`` path.

        Returns:
            Resolved path written.

        Raises:
            RuntimeError: When no workbook has been created.
            OSError: When the file cannot be written.
        """
        if self._target is None:
            raise RuntimeError("create_workbook must be called before save")

        destination = Path(path)
        ensure_directory(destination.parent)
        self._target.workbook.save(destination)
        _logger.debug("Saved workbook to %s", destination)
        return destination.resolve()

    def close(self) -> None:
        """Drop the in-memory workbook reference."""
        self._target = None
