"""Workbook reading layer.

Isolates Excel / spreadsheet I/O from import orchestration and domain mapping.
The public surface is library-agnostic so backends can be swapped without
changing a future Excel import service.

Public API
----------
* :class:`WorkbookReader` — reading protocol
* :class:`OpenPyxlWorkbookReader` — openpyxl backend
"""

from __future__ import annotations

from classroom_library_label_maker.workbooks.openpyxl_workbook_reader import (
    OpenPyxlWorkbookReader,
)
from classroom_library_label_maker.workbooks.workbook_reader import WorkbookReader

__all__ = [
    "OpenPyxlWorkbookReader",
    "WorkbookReader",
]
