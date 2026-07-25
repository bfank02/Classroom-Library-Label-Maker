"""Service-layer components for barcode generation.

Canonical pipeline for new development (Feature 6+)::

* :class:`ExcelImportService`
* :class:`BatchProcessingService`
* :class:`LabelLayoutService`
* :class:`WorkbookGenerationService` (end-to-end orchestration)

Also stable: :class:`IsbnValidator`, :class:`BarcodeGenerationService`.

Deprecated / internal (CLI compatibility only — do not use for new work):

* :class:`BatchProcessor`
* :class:`BarcodeGenerator`

Extension protocols live in ``services.protocols``; future providers belong
under ``services.lookups`` and ``services.covers``.
"""

from __future__ import annotations

from classroom_library_label_maker.services.barcode_generation_service import (
    BarcodeGenerationService,
)
from classroom_library_label_maker.services.barcode_generator import BarcodeGenerator
from classroom_library_label_maker.services.batch_processing_service import (
    BatchProcessingService,
)
from classroom_library_label_maker.services.batch_processor import BatchProcessor
from classroom_library_label_maker.services.excel_import_service import (
    ExcelImportService,
)
from classroom_library_label_maker.services.isbn_validator import (
    ISBNValidator,
    IsbnValidator,
)
from classroom_library_label_maker.services.label_layout_service import (
    LabelLayoutService,
)
from classroom_library_label_maker.services.workbook_generation_service import (
    WorkbookGenerationService,
)

__all__ = [
    "BarcodeGenerationService",
    "BarcodeGenerator",
    "BatchProcessingService",
    "BatchProcessor",
    "ExcelImportService",
    "ISBNValidator",
    "IsbnValidator",
    "LabelLayoutService",
    "WorkbookGenerationService",
]
