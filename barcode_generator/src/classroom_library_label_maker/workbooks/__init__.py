"""Workbook / worksheet I/O layer.

Isolates Excel spreadsheet access from import and layout orchestration.
The public surface is library-agnostic so backends can be swapped without
changing services.

Public API
----------
* :class:`WorkbookReader` / :class:`OpenPyxlWorkbookReader` — workbook reading
* :class:`WorkbookWriter` / :class:`OpenPyxlWorkbookWriter` — workbook create/save
* :class:`LabelSheetTarget` / :class:`LabelPlacement` — label placement contract
* :class:`InMemoryLabelSheetTarget` / :class:`InMemoryWorkbookWriter` — tests
* :class:`OpenPyxlLabelSheetTarget` — openpyxl placement (used by writer)
"""

from __future__ import annotations

from classroom_library_label_maker.workbooks.in_memory_label_sheet_target import (
    InMemoryLabelSheetTarget,
)
from classroom_library_label_maker.workbooks.in_memory_workbook_writer import (
    InMemoryWorkbookWriter,
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
from classroom_library_label_maker.workbooks.openpyxl_workbook_writer import (
    OpenPyxlWorkbookWriter,
)
from classroom_library_label_maker.workbooks.workbook_reader import WorkbookReader
from classroom_library_label_maker.workbooks.workbook_writer import WorkbookWriter

__all__ = [
    "InMemoryLabelSheetTarget",
    "InMemoryWorkbookWriter",
    "LabelPlacement",
    "LabelSheetTarget",
    "OpenPyxlLabelSheetTarget",
    "OpenPyxlWorkbookReader",
    "OpenPyxlWorkbookWriter",
    "WorkbookReader",
    "WorkbookWriter",
]
