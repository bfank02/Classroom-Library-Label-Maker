"""In-memory :class:`WorkbookWriter` for tests (no Excel I/O)."""

from __future__ import annotations

from pathlib import Path

from classroom_library_label_maker.workbooks.in_memory_label_sheet_target import (
    InMemoryLabelSheetTarget,
)
from classroom_library_label_maker.workbooks.label_sheet_target import LabelSheetTarget


class InMemoryWorkbookWriter:
    """Record create/save/close without touching the filesystem by default.

    ``save`` records the requested path and optionally writes a tiny marker
    file when ``write_marker`` is True (for path-existence assertions).
    """

    def __init__(self, *, write_marker: bool = False) -> None:
        """Initialize the fake writer.

        Args:
            write_marker: When True, ``save`` creates an empty file at ``path``.
        """
        self._target: InMemoryLabelSheetTarget | None = None
        self._write_marker = write_marker
        self.created = False
        self.closed = False
        self.saved_path: Path | None = None
        self.save_calls = 0

    def create_workbook(self) -> None:
        """Create an in-memory label sheet target."""
        self._target = InMemoryLabelSheetTarget()
        self.created = True
        self.closed = False
        self.saved_path = None

    def get_label_sheet_target(self) -> LabelSheetTarget:
        """Return the in-memory label sheet target."""
        if self._target is None:
            raise RuntimeError("create_workbook must be called before get_label_sheet_target")
        return self._target

    def save(self, path: Path) -> Path:
        """Record a save (and optionally write a marker file)."""
        if self._target is None:
            raise RuntimeError("create_workbook must be called before save")
        destination = Path(path)
        self.save_calls += 1
        self.saved_path = destination.resolve() if destination.is_absolute() else destination
        if self._write_marker:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"")
        return destination

    def close(self) -> None:
        """Mark the writer closed and drop the target."""
        self._target = None
        self.closed = True
