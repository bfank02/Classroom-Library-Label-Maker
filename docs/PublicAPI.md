# Public API

Public surface of the **Classroom Library Label Maker** barcode generator
package (`classroom_library_label_maker`).

Prefer importing from documented submodules
(`models`, `services`, `rendering`, `workbooks`, `label_templates`,
`exceptions`, `config`, `metadata`).
The package root re-exports a narrow set of common types.

## Stability legend

| Label | Meaning |
|-------|---------|
| **Stable** | Intended for consumption by future features (Excel, CLI, labels). Backward-compatible unless a major version bump. |
| **Experimental** | Usable, but shape may change as adjacent features land. |
| **Internal** | Infrastructure or transitional API. Prefer not to depend on it from new call sites. |

---

## Domain Models

Module: `classroom_library_label_maker.models`

### `Book` — Stable — External

**Purpose:** Classroom library book record passed into validation, generation,
and batch orchestration.

**Public methods**

| Method | Inputs | Outputs |
|--------|--------|---------|
| `from_dict(data)` | JSON-like mapping (`isbn` or legacy `isbn13`, `title`, `author`, …) | `Book` |
| `to_dict()` | — | JSON-compatible `dict` |

**Fields (inputs/outputs):** `isbn`, `title`, `author`, `copies`, optional
`genre`, `reading_level`, `location`, `condition`.

### `ValidationResult` — Stable — External

**Purpose:** Outcome of validating one ISBN (never raises for expected invalid
input).

**Fields:** `isbn`, `is_valid`, `errors`, `error_code`.

### `ValidationErrorCode` — Stable — External

**Purpose:** Machine-readable ISBN failure codes; `.message` is the default
user-facing text.

### `BarcodeStatus` — Stable — External

**Purpose:** Outcome enum for a single barcode generation attempt
(`GENERATED`, `ALREADY_EXISTS`, `INVALID_ISBN`, `ERROR`, `SKIPPED`).

### `BarcodeGenerationResult` — Stable — External

**Purpose:** Result of generating (or skipping) one barcode image.

**Public methods:** `to_dict()`.

**Fields:** `isbn`, `status`, `output_path`, `message`, `title`.

### `BookProcessingStatus` — Stable — External

**Purpose:** Per-book status inside a batch (`GENERATED`, `ALREADY_EXISTS`,
`VALIDATION_FAILED`, `GENERATION_FAILED`).

### `BookProcessingResult` — Stable — External

**Purpose:** Combined validation + generation outcome for one book in a batch.

**Public methods:** `to_dict()`.

**Fields:** `isbn`, `title`, `status`, `output_path`, `message`, optional
`validation`, `generation`.

### `BatchProcessingResult` — Stable — External

**Purpose:** Aggregate batch outcome (ordered results + timing + counts).

**Derived properties:** `total_processed`, `successful_generations`,
`existing_barcodes_skipped`, `validation_failures`, `generation_failures`,
`books_per_second` (safe on zero elapsed time).

**Public methods:** `to_dict()`.

**Fields:** `results` (input order), `elapsed_seconds`.

### `ApplicationSettings` — Stable — External

**Purpose:** Project paths, logging, and barcode render geometry for a run.

**Construction:** Prefer `config.load_application_settings(...)`.

**Notable fields:** `barcode_output_directory`, `log_directory`,
`barcode_module_width` / `height` / `quiet_zone` / `font_size` / `dpi`,
optional `input_path` / `results_path`.

### `BatchResults` — Experimental — External (legacy CLI)

**Purpose:** Older aggregate used by `BatchProcessor.write_results`. Prefer
`BatchProcessingResult` for new orchestration.

### `IsbnLookupResult` / `CoverImageResult` — Experimental — External

**Purpose:** Reserved result shapes for future enrichment providers.

---

## Validation

Module: `classroom_library_label_maker.services.isbn_validator`

### `IsbnValidator` (alias `ISBNValidator`) — Stable — External

**Purpose:** Normalize and validate ISBN-13 values. Stateless. Does not raise
for expected invalid ISBNs.

| Method | Stability | Inputs | Outputs |
|--------|-----------|--------|---------|
| `normalize(isbn)` | **Stable** | `str \| None` | Digits-only string (may be empty) |
| `validate(isbn)` | **Stable** | `str \| None` | `ValidationResult` |
| `validate_many(isbns)` | **Stable** | iterable of `str \| None` | `list[ValidationResult]` (order preserved) |
| `is_valid(isbn)` | Experimental | `str \| None` | `bool` |
| `compute_check_digit(first_twelve_digits)` | Experimental | 12-digit string | Check digit `str` (may raise `ValueError`) |

---

## Barcode Generation

Module: `classroom_library_label_maker.services.barcode_generation_service`

### `BarcodeGenerationService` — Stable — External

**Purpose:** Create EAN-13 PNG files for a **validated** `Book`. Does not
re-validate ISBNs. Does not import third-party barcode libraries directly.

| Method | Inputs | Outputs / errors |
|--------|--------|------------------|
| `__init__(settings, *, renderer=None, …)` | `ApplicationSettings`; optional `BarcodeRenderer` | service |
| `generate_for_book(book)` | Validated `Book` | `BarcodeGenerationResult` (`GENERATED` or `ALREADY_EXISTS`); may raise `FileSystemError` / `BarcodeGenerationError` |
| `output_path_for(isbn)` | Normalized ISBN stem | `Path` to `{dir}/{isbn}.png` |

**External use:** Yes — primary generation API for all future features.

---

## Batch Processing

Module: `classroom_library_label_maker.services.batch_processing_service`

### `BatchProcessingService` — Stable — External

**Purpose:** Orchestrate validation + generation over a collection of books.
Continues after per-book failures. Preserves input order.

| Method | Inputs | Outputs |
|--------|--------|---------|
| `__init__(settings, *, validator=None, generator=None, progress_reporter=None, cancellation_token=None)` | Settings + optional overrides / hooks | service |
| `process_books(books)` | `Sequence[Book]` (may be empty) | `BatchProcessingResult` |

**Notes**

- `progress_reporter`: optional; see Protocols.
- `cancellation_token`: accepted for API stability; **not enforced** yet.

**External use:** Yes — orchestration layer for future Excel import.

---

## Rendering

Module: `classroom_library_label_maker.rendering`

### `BarcodeRenderer` — Stable — External (protocol)

**Purpose:** Library-agnostic contract for writing barcode images.

| Method | Inputs | Outputs |
|--------|--------|---------|
| `render_to_file(data, output_path, *, symbology=EAN13)` | Payload string, destination path, symbology | `Path` written |

### `BarcodeSymbology` — Stable — External

**Purpose:** Symbology identifiers. `EAN13` implemented; `CODE128` / `QR`
reserved.

### `PythonBarcodeRenderer` — Stable — External (default backend)

**Purpose:** EAN-13 PNG backend via python-barcode + Pillow. Keeps vendor
types inside the rendering layer.

| Method | Inputs | Outputs |
|--------|--------|---------|
| `__init__(*, module_width, module_height, quiet_zone, font_size, dpi)` | Geometry (defaults from constants) | renderer |
| `from_settings(settings)` | `ApplicationSettings` | renderer |
| `render_to_file(...)` | Same as protocol | `Path`; may raise `ValueError` / `OSError` |

**External use:** Prefer depending on `BarcodeRenderer` in services; construct
`PythonBarcodeRenderer` only when injecting a concrete backend.

---

## Services

Package: `classroom_library_label_maker.services`

| Type | Stability | Audience | Purpose |
|------|-----------|----------|---------|
| `IsbnValidator` | Stable | External | ISBN validation |
| `BarcodeGenerationService` | Stable | External | Single-book PNG generation |
| `BatchProcessingService` | Stable | External | Multi-book orchestration |
| `ExcelImportService` | Stable | External | Workbook → `Book` import |
| `BatchProcessor` | Experimental | Internal / transitional | CLI/JSON adapter (`load_books` still stubbed) |
| `BarcodeGenerator` | Internal | Transitional | Legacy path helpers; superseded by `BarcodeGenerationService` |

---

## Protocols

Module: `classroom_library_label_maker.services.protocols`

### `BatchProgressReporter` — Stable — External

**Purpose:** Optional progress hooks for CLI/UI without changing
`process_books()`.

| Method | Inputs |
|--------|--------|
| `on_batch_started(total)` | Book count |
| `on_book_processed(index, total, result)` | 1-based index + `BookProcessingResult` |
| `on_batch_completed(total)` | Book count |

### `BatchCancellationToken` — Experimental — External

**Purpose:** Cooperative cancellation extension point.

| Method | Outputs |
|--------|---------|
| `is_cancellation_requested()` | `bool` |

**Status:** Accepted by `BatchProcessingService` but **not enforced** yet.

### `IsbnLookupService` / `CoverDownloadService` — Experimental — External

**Purpose:** Future enrichment contracts (`lookup`, `download`).

---

## Workbooks

Module: `classroom_library_label_maker.workbooks`

Spreadsheet I/O only. Does **not** map rows to `Book` (that belongs to a
future Excel import service).

### `WorkbookReader` — Stable — External (protocol)

**Purpose:** Library-agnostic contract for opening workbooks and reading rows
as plain string cells.

| Method | Inputs | Outputs |
|--------|--------|---------|
| `open(path)` | `Path` | — |
| `close()` | — | — |
| `sheet_names()` | — | `Sequence[str]` |
| `iter_rows(sheet_name, *, min_row=1)` | Sheet name, optional start row | Iterator of `(str \| None, ...)` |

### `OpenPyxlWorkbookReader` — Stable — External (default backend)

**Purpose:** openpyxl backend returning plain string cells only.

**External use:** Prefer depending on `WorkbookReader` in services; construct
`OpenPyxlWorkbookReader` when injecting the concrete backend.

### `ExcelImportService` — Stable — External

Module: `classroom_library_label_maker.services.excel_import_service`

**Purpose:** Import `Book` rows from a workbook via `WorkbookReader`. Does not
validate ISBNs or generate barcodes.

| Method | Inputs | Outputs / errors |
|--------|--------|------------------|
| `__init__(settings, *, reader=None)` | `ApplicationSettings`; optional reader | service |
| `import_books(workbook_path=None)` | Optional path override | `ImportResult`; may raise `ConfigurationError`, `FileSystemError`, `InvalidWorkbookError` |

Configuration (on `ApplicationSettings`): `workbook_path`, `workbook_sheet_name`,
`workbook_column_*`, `workbook_header_row`.

### `ImportResult` / `ImportWarning` — Stable — External

**Purpose:** Import outcome (`books`, `source_rows`, row counts, warnings,
`elapsed_seconds`) and recoverable per-row diagnostics.

Both are **immutable value objects** (`dataclass(frozen=True)`). Callers should
treat instances as read-only after construction.

### Workbook template versioning — Experimental — Extension point

**Not implemented.** Future template version checks belong in
`ExcelImportService.import_books` after open/sheet selection and before column
mapping. Version metadata may live in a Meta sheet cell, document properties,
or similar — see Architecture.md. Multiple template versions can later select
different column maps via settings without changing `WorkbookReader`.

---

## Label templates

Module: `classroom_library_label_maker.label_templates`

Physical sheet geometry only (inches). No Excel, rendering, or printing.

### `LabelTemplate` — Stable — External (protocol)

**Purpose:** Immutable physical specification of a label sheet.

Identification: `template_id`, `template_name`, `vendor`, `product_number`,
`description`.  
Page: `page_size`, `orientation`, `page_width`, `page_height`.  
Layout: `rows`, `columns`, `label_width`, `label_height`, margins, gaps.  
Derived: `labels_per_page`, `printable_width`, `printable_height`.

### `LabelTemplateSpec` — Stable — External

**Purpose:** Frozen dataclass implementing `LabelTemplate`.

### `TemplateRegistry` — Stable — External

| Method | Behavior |
|--------|----------|
| `register(template)` | Register by `template_id` |
| `get(template_id)` | Lookup; raises `ConfigurationError` if unknown |
| `list_templates()` | Sorted tuple of registered templates |

`create_default_template_registry()` registers `AVERY_5160` (`avery-5160`).

### `AVERY_5160` / `Avery5160` — Stable — External

**Purpose:** Built-in Avery 5160 layout data (Letter, 3×10, 1×2.625 in).

---

## Exceptions

Module: `classroom_library_label_maker.exceptions` — Stable — External

```
ApplicationError
├── ConfigurationError
├── ValidationError
│   ├── InvalidISBNError
│   └── InvalidWorkbookError
├── BarcodeGenerationError
└── FileSystemError
```

Use these for unexpected failures. Expected invalid ISBNs use
`ValidationResult`, not exceptions.

---

## Related docs

- [Architecture](Architecture.md)
- [Developer Review Checklist](DeveloperReviewChecklist.md)
- [Feature Review Template](templates/FeatureReviewTemplate.md)
- [FDR-002 Barcode Generation](decisions/FDR-002-barcode-generation.md)
