# Public API

Public surface of the **Classroom Library Label Maker** barcode generator
package (`classroom_library_label_maker`).

Prefer importing from documented submodules
(`models`, `services`, `rendering`, `workbooks`, `label_templates`,
`exceptions`, `config`, `metadata`).
The package root re-exports a narrow set of common types.

## Canonical workflow (Feature 6)

```
ExcelImportService
        ↓
BatchProcessingService
        ↓
WorkbookWriter + LabelLayoutService
        ↓
WorkbookWriter.save → label workbook (.xlsx)
```

Orchestrated by `WorkbookGenerationService`.

Supporting stables: `IsbnValidator`, `BarcodeGenerationService`,
`LabelTemplate` / `TemplateRegistry`, `WorkbookReader`, `WorkbookWriter`,
`LabelSheetTarget`.

**Implemented:** import, validate, generate barcodes, batch orchestration,
label layout, label workbook **save**, CLI `generate` via
`WorkbookGenerationService`.

**Not implemented:** **printing** / print preview, Excel VBA UI.

**Deprecated (unused by CLI — transitional only):**
`BatchProcessor`, `BarcodeGenerator`, `BatchResults`.

## Stability legend

| Label | Meaning |
|-------|---------|
| **Stable** | Intended for Feature 6+ and library callers. Backward-compatible unless a major version bump. |
| **Experimental** | Usable, but shape may change as adjacent features land. |
| **Internal / Deprecated** | Legacy or transitional. Do not depend on it from new call sites. |

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

### `LabelLayoutResult` / `LabelLayoutWarning` — Stable — External

**Purpose:** Outcome of arranging books onto label worksheet pages, plus
recoverable diagnostics (e.g. missing barcode images).

**Public methods:** `to_dict()`.

**Fields:** `pages_created`, `labels_placed`,
`empty_labels_remaining_on_last_page`, `elapsed_seconds`, `warnings`,
`template_id`.

### `WorkbookGenerationResult` / `WorkbookGenerationWarning` — Stable — External

**Purpose:** End-to-end generation outcome and recoverable diagnostics.

**Public methods:** `to_dict()`.

**Fields:** `books_imported`, `books_processed`, `labels_created`,
`pages_created`, `barcodes_generated`, `barcodes_reused`, `output_path`,
`elapsed_seconds`, `warnings`.

### `ApplicationSettings` — Stable — External

**Purpose:** Project paths, logging, barcode render geometry, workbook import,
and label template selection for a run.

**Construction:** Prefer `config.load_application_settings(...)`.

**Notable fields:**

| Field | Role |
|-------|------|
| `label_template_id` | **Single source of truth** for `LabelLayoutService` / `TemplateRegistry` (default `avery-5160`) |
| `default_label_type` | **Deprecated** compatibility field; not used by layout |
| `workbook_path`, `workbook_sheet_name`, `workbook_column_*`, `workbook_header_row` | Excel import |
| `barcode_output_directory`, `barcode_module_*` / `quiet_zone` / `font_size` / `dpi` | Barcode output + render geometry |
| `input_path` / `results_path` | Legacy CLI JSON paths |

### `BatchResults` — Internal / Deprecated

**Purpose:** Older aggregate used only by deprecated `BatchProcessor.write_results`.
**Do not use for new development.** Prefer `BatchProcessingResult`.

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

**External use:** Yes — primary generation API for Feature 6+ and library callers.

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

**External use:** Yes — canonical multi-book orchestration after Excel import.

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
| `BatchProcessingService` | Stable | External | Multi-book orchestration (canonical) |
| `ExcelImportService` | Stable | External | Workbook → `Book` import |
| `LabelLayoutService` | Stable | External | Arrange books onto label sheets |
| `WorkbookGenerationService` | Stable | External | End-to-end import → barcodes → layout → save (canonical runtime / CLI) |
| `BatchProcessor` | Internal / Deprecated | Unused by CLI | Legacy JSON stub; do not use |
| `BarcodeGenerator` | Internal / Deprecated | Unused by CLI | Legacy stub; superseded by `BarcodeGenerationService` |

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

Spreadsheet I/O only. Row → `Book` mapping belongs to `ExcelImportService`.
Label placement writes belong to `LabelLayoutService` via `LabelSheetTarget`.

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

### `WorkbookWriter` — Stable — External (protocol)

**Purpose:** Library-agnostic contract for creating a label workbook, exposing
a `LabelSheetTarget` for layout, and saving to disk.

| Method | Inputs | Outputs |
|--------|--------|---------|
| `create_workbook()` | — | — |
| `get_label_sheet_target()` | — | `LabelSheetTarget` |
| `save(path)` | Destination `Path` | `Path` written |
| `close()` | — | — |

### `OpenPyxlWorkbookWriter` — Stable — External (default write backend)

**Purpose:** openpyxl create/save adapter. Owns an `OpenPyxlLabelSheetTarget`
for placement. **Does not print.**

### `InMemoryWorkbookWriter` — Stable — External

**Purpose:** Test double that records create/save/close (optional marker file).

### `LabelSheetTarget` — Stable — External (protocol)

**Purpose:** Library-agnostic contract for creating label pages and placing
labels. Layout services must not depend on openpyxl worksheet objects.

| Method | Inputs | Outputs |
|--------|--------|---------|
| `begin_page(page_number, *, template)` | 1-based page, `LabelTemplate` | — |
| `place_label(placement)` | `LabelPlacement` | — |

### `LabelPlacement` — Stable — External

**Purpose:** Immutable placement payload: page/row/column, title, author, ISBN,
optional barcode path, and placeholder flag.

### `InMemoryLabelSheetTarget` — Stable — External

**Purpose:** Records pages and placements for tests / non-Excel consumers.

### `OpenPyxlLabelSheetTarget` — Stable — External (default write backend)

**Purpose:** Place centered title/author/ISBN (and optional barcode image) onto
openpyxl worksheets. Persisting the workbook is the job of
`OpenPyxlWorkbookWriter` / `WorkbookWriter.save`.

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

### `LabelLayoutService` — Stable — External

Module: `classroom_library_label_maker.services.label_layout_service`

**Purpose:** Arrange `Book` objects onto worksheet pages using `LabelTemplate`
and `LabelSheetTarget`. Does not generate barcodes, validate ISBNs, import
workbooks, print, or save.

| Method | Inputs | Outputs / errors |
|--------|--------|------------------|
| `__init__(settings, *, registry=None)` | `ApplicationSettings`; optional registry | service |
| `layout_books(books, target, *, template=None, barcode_paths=None)` | Books, target, optional template / ISBN→PNG map | `LabelLayoutResult`; may raise `ConfigurationError`, `LabelLayoutError` |

Uses `settings.label_template_id` (canonical template setting) when `template`
is omitted. Missing barcode images become placeholders with warnings
(`missing_barcode`, `barcode_file_missing`).

**Does not** print or save workbooks (save belongs to `WorkbookWriter`).

### `LabelLayoutResult` / `LabelLayoutWarning` — Stable — External

**Purpose:** Layout outcome (`pages_created`, `labels_placed`,
`empty_labels_remaining_on_last_page`, `elapsed_seconds`, `warnings`,
`template_id`) and recoverable diagnostics.

Both are **immutable value objects** (`dataclass(frozen=True)`).

### `WorkbookGenerationService` — Stable — External

Module: `classroom_library_label_maker.services.workbook_generation_service`

**Purpose:** End-to-end orchestration: import inventory → process barcodes →
layout labels → save label workbook. Does not print or display UI.

| Method | Inputs | Outputs / errors |
|--------|--------|------------------|
| `__init__(settings, *, importer=None, batch_processor=None, layout_service=None, writer=None)` | Settings + optional collaborators | service |
| `generate(*, workbook_path=None, output_path=None)` | Optional inventory / output overrides | `WorkbookGenerationResult`; may raise `ConfigurationError`, `FileSystemError`, `InvalidWorkbookError`, `LabelLayoutError`, `WorkbookGenerationError` |

Default `output_path`: `{project_root}/output/library_labels.xlsx`.

The CLI `generate` command invokes this service only (thin adapter).

---

## CLI

Module: `classroom_library_label_maker.cli` / entry `main.py`

**Canonical runtime:** `WorkbookGenerationService` (no `BatchProcessor`).

### `generate` — Stable

| Flag | Role |
|------|------|
| `--input` / `-i` | Inventory Excel workbook (required) |
| `--output-dir` / `-o` | Barcode PNG directory |
| `--labels-output` / `-l` | Label workbook path (default under `output/`) |
| `--results` / `-r` | Optional JSON summary (`WorkbookGenerationResult.to_dict`) |
| `--overwrite` | Regenerate existing barcode PNGs |
| `--log-level`, `--log-file` | Logging |

Omitting a subcommand still maps flat flags to `generate`.

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Invalid arguments |
| `2` | Input / import failure |
| `3` | Generation failure (barcodes, layout, or save) |
| `4` | Unexpected internal error |
| `5` | Reserved command not implemented |

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
Select templates via `ApplicationSettings.label_template_id` (not
`default_label_type`).

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
├── LabelLayoutError
├── WorkbookGenerationError
└── FileSystemError
```

Use these for unexpected failures. Expected invalid ISBNs use
`ValidationResult`, not exceptions. Recoverable layout/generation issues use
warning objects inside result types.

---

## Related docs

- [Architecture](Architecture.md)
- [Developer Review Checklist](DeveloperReviewChecklist.md)
- [Feature Review Template](templates/FeatureReviewTemplate.md)
- [FDR-002 Barcode Generation](decisions/FDR-002-barcode-generation.md)
