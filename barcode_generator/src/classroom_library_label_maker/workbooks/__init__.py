"""Workbook / worksheet I/O layer.

Isolates Excel spreadsheet access from import and layout orchestration.
The public surface is library-agnostic so backends can be swapped without
changing services.

Public API
----------
* :class:`WorkbookReader` / :class:`OpenPyxlWorkbookReader` — workbook reading
* :class:`LabelSheetTarget` / :class:`LabelPlacement` — label placement contract
* :class:`InMemoryLabelSheetTarget` — test / non-Excel target
* :class:`OpenPyxlLabelSheetTarget` — openpyxl placement (no save)
"""

from __future__ import annotations

from classroom_library_label_maker.workbooks.in_memory_label_sheet_target import (
    InMemoryLabelSheetTarget,
)
from classroom_library_label_maker.workbooks.label_sheet_target import (
    LabelPlacement,
    LabelSheetTarget,
)
from classroom_library_label_maker.workbooks.openpyxl_label_sheet_target import (
    OpenPyxlLabelSheetTarget,
)
from classroom_library_label_maker.workbooks.openpyxl_workbook_reader import (
    OpenPyxlWorkbookReader,
)
from classroom_library_label_maker.workbooks.workbook_reader import WorkbookReader

__all__ = [
    "InMemoryLabelSheetTarget",
    "LabelPlacement",
    "LabelSheetTarget",
    "OpenPyxlLabelSheetTarget",
    "OpenPyxlWorkbookReader",
    "WorkbookReader",
]
