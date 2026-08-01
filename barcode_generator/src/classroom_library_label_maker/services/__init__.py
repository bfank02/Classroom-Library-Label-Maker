"""Service-layer components for barcode generation.

Canonical pipeline for new development and the CLI ``generate`` command::

* :class:`WorkbookGenerationService` (end-to-end orchestration)
* :class:`ExcelImportService`
* :class:`BatchProcessingService`
* :class:`LabelLayoutService`

Also stable: :class:`IsbnValidator`, :class:`BarcodeGenerationService`.

Experimental enrichment (not wired into generation yet):

* :class:`BookEnrichmentService`
* :class:`NullBookEnrichmentProvider`
* :class:`GoogleBooksEnrichmentProvider` (``services.lookups``)

Deprecated / unused by the CLI (kept for transitional imports only):

* :class:`BatchProcessor`
* :class:`BarcodeGenerator`

Extension protocols live in ``services.protocols``; catalog providers belong
under ``services.lookups`` and cover providers under ``services.covers``.
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
from classroom_library_label_maker.services.book_enrichment_service import (
    BookEnrichmentService,
    NullBookEnrichmentProvider,
    create_default_enrichment_service,
)
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
from classroom_library_label_maker.services.lookups import (
    GoogleBooksEnrichmentProvider,
)
from classroom_library_label_maker.services.workbook_generation_service import (
    WorkbookGenerationService,
)

__all__ = [
    "BarcodeGenerationService",
    "BarcodeGenerator",
    "BatchProcessingService",
    "BatchProcessor",
    "BookEnrichmentService",
    "ExcelImportService",
    "GoogleBooksEnrichmentProvider",
    "ISBNValidator",
    "IsbnValidator",
    "LabelLayoutService",
    "NullBookEnrichmentProvider",
    "WorkbookGenerationService",
    "create_default_enrichment_service",
]
