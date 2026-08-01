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
(optional) BookEnrichmentService   # lookup_missing_isbns (default on)
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

**Implemented:** import, optional missing-ISBN enrichment, validate, generate
barcodes, batch orchestration, label layout, label workbook **save**, CLI
`generate` and desktop GUI via `WorkbookGenerationService`, with stage
progress reporting (including **"Looking up missing ISBNs..."**).

**Not implemented:** **printing** / print preview, Excel VBA UI; GUI
cancellation; CLI progress printing (reporter hooks exist).

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
`pdf_output_path`, `elapsed_seconds`, `warnings`, optional `enrichment`
(`EnrichmentSummary`), `books` (post-enrichment, import order),
`source_rows` (matching 1-based Excel rows for inventory updates).

### `EnrichmentSummary` — Experimental — External

**Purpose:** Shared ISBN enrichment counts for one generation run (GUI/CLI/logs).

**Fields:** `enabled`, `books_with_isbn`, `books_looked_up`, `isbns_found`,
`ambiguous_matches`, `not_found`, `lookup_errors`, `cache_hits`,
`cache_misses`, `review_items`.

**Derived:** `needs_review_count` = `len(review_items)`.

### `ReviewCandidate` — Experimental — External

**Purpose:** One catalog match preserved during enrichment for a future
interactive review UI (no extra Google Books requests at review time).

**Fields:** `isbn13`, `isbn10`, `title`, `author`, `publisher`,
`published_date`, `confidence_score` (internal `[0, 1]` match score — not for
direct UI interpretation).

**Derived:** `confidence_label` → `Very High` / `High` / `Medium` / `Low`
via `confidence_label_for_score` (single source of truth). Display as
`"{confidence_label} Match"` in GUI/CLI when the review UI lands.

Frozen dataclass. Serialized via `to_dict()` (includes both
`confidence_score` and `confidence_label`).

### `confidence_label_for_score` — Experimental — External

**Purpose:** Map a numeric confidence score to a presentation label. Prefer
`ReviewCandidate.confidence_label`; call this helper only when you have a
raw score outside a candidate instance.

Thresholds (inclusive lower bounds): ≥0.90 Very High, ≥0.80 High,
≥0.70 Medium, else Low.

### `ReviewItem` — Experimental — External

**Purpose:** One book that still needs teacher attention after automatic ISBN
lookup (`AMBIGUOUS`, `NOT_FOUND`, or `ERROR`). Successful finds are omitted.

**Fields:** `title`, `author`, `status` (`BookEnrichmentStatus`), `message`
(short explanation), `candidates` (`tuple[ReviewCandidate, ...]`, populated
for ambiguous matches; empty otherwise), optional `book` (original
inventory `Book` when produced by generation — used to seed
`ReviewSession`).

GUI/CLI show an **ISBN Lookup Summary** (found count, needs-review count, up
to five titles, then `...and X more.`) when `review_items` is non-empty.
After generation, the desktop app opens `ReviewWizardDialog` when items
carry books for interactive review.

### `ReviewDecision` — Experimental — External

**Purpose:** One teacher action for a single review queue entry.

**Fields:** `book` (original), `candidate` (optional `ReviewCandidate`),
`skipped` (bool). Exactly one of skip vs candidate must be set.

Frozen dataclass. Serialized via `to_dict()`.

### `ReviewSessionResult` — Experimental — External

**Purpose:** Outcome of applying a finished `ReviewSession` via
`BookReviewService`.

**Fields:** `updated_books`, `resolved_count`, `skipped_count`,
`unresolved_count`, `total_reviewed` (`resolved + skipped`).

Frozen dataclass. Serialized via `to_dict()`.

### `ApplicationSettings` — Stable — External

**Purpose:** Project paths, logging, barcode render geometry, workbook import,
label template selection, and enrichment options for a run.

**Construction:** Prefer `config.load_application_settings(...)`.

**Notable fields:**

| Field | Role |
|-------|------|
| `label_template_id` | **Single source of truth** for `LabelLayoutService` / `TemplateRegistry` (default `avery-5160`) |
| `default_label_type` | **Deprecated** compatibility field; not used by layout |
| `workbook_path`, `workbook_sheet_name`, `workbook_column_*`, `workbook_header_row` | Excel import |
| `barcode_output_directory`, `barcode_module_*` / `quiet_zone` / `font_size` / `dpi` | Barcode output + render geometry |
| `lookup_missing_isbns` | When True (default), look up blank ISBNs during generation |
| `input_path` / `results_path` | Legacy CLI JSON paths |

### `BatchResults` — Internal / Deprecated

**Purpose:** Older aggregate used only by deprecated `BatchProcessor.write_results`.
**Do not use for new development.** Prefer `BatchProcessingResult`.

### `BookEnrichmentStatus` — Experimental — External

**Purpose:** Outcome codes for one enrichment attempt:
`FOUND`, `NOT_FOUND`, `SKIPPED`, `AMBIGUOUS`, `ERROR`.

### `BookEnrichmentResult` — Experimental — External

**Purpose:** Immutable enrichment outcome for one `Book`. Core fields cover
common catalog metadata; `metadata` holds additive key/value pairs without
requiring a model redesign when new providers land.

**Fields:** `isbn`, `status`, optional `title` / `author`, `message`,
`metadata`, `candidates` (`tuple[ReviewCandidate, ...]`; set for
`AMBIGUOUS`, empty for successful `FOUND`).

| Method | Outputs |
|--------|---------|
| `to_dict()` | JSON-compatible `dict` (copies `metadata` and candidates) |

**Notes**

- Frozen dataclass (`frozen=True`, `slots=True`).
- Providers must not mutate the input `Book`; return a new result instead.
- Prefer this model over `IsbnLookupResult` for new enrichment pipelines.
- Candidate lists are produced once during enrichment and reused via the
  enrichment cache / `ReviewItem` for interactive review.

### `IsbnLookupResult` / `CoverImageResult` — Experimental — External

**Purpose:** Reserved result shapes for narrower ISBN-string lookup and cover
download providers. Prefer `BookEnrichmentResult` for book enrichment.

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
| `WorkbookGenerationService` | Stable | External | End-to-end import → barcodes → layout → save (canonical runtime for CLI and desktop GUI) |
| `BookEnrichmentService` | Experimental | External | Provider-agnostic book enrichment (used by generation when lookup enabled) |
| `NullBookEnrichmentProvider` | Experimental | External | Default no-op provider (`SKIPPED`; preserves Version 1.0 behavior) |
| `GoogleBooksEnrichmentProvider` | Experimental | External | Google Books title/author enrichment (optional; not default) |
| `ReviewSession` | Experimental | External | UI-independent interactive review queue / decisions |
| `BookReviewService` | Experimental | External | Apply finished review decisions → updated `Book`s |
| `InventoryUpdateService` | Experimental | External | Write updated inventory workbook copy after review |
| `BatchProcessor` | Internal / Deprecated | Unused by CLI | Legacy JSON stub; do not use |
| `BarcodeGenerator` | Internal / Deprecated | Unused by CLI | Legacy stub; superseded by `BarcodeGenerationService` |

### `BookEnrichmentService` — Experimental — External

Module: `classroom_library_label_maker.services.book_enrichment_service`

**Purpose:** Delegate enrichment of a `Book` to a `BookEnrichmentProvider`.
Defaults to `NullBookEnrichmentProvider` when constructed alone. Generation
uses `create_default_enrichment_service()` (Google Books) when
`lookup_missing_isbns` is True.

| Method | Inputs | Outputs |
|--------|--------|---------|
| `__init__(*, provider=None)` | Optional `BookEnrichmentProvider` | service |
| `enrich(book)` | `Book` | `BookEnrichmentResult` (cached on normalized title+author) |
| `enrich_many(books)` | `Sequence[Book]` | `list[BookEnrichmentResult]` (order preserved; uses same cache) |
| `provider` (property) | — | configured provider |
| `cache_hits` / `cache_misses` / `cache_size` | — | diagnostic counters (testing/logging only) |

**Notes**

- In-memory cache only (no disk). Key = normalized title + author (not ISBN).
- All result statuses are cached. Providers are not called on cache hit.
- Used by `WorkbookGenerationService` when `lookup_missing_isbns` is enabled.

### `ReviewSession` — Experimental — External

Module: `classroom_library_label_maker.services.book_review_service`

**Purpose:** Own interactive review state (current item, navigation, decisions,
completion). Construct from parallel `Book` / `ReviewItem` sequences or
`ReviewSession.from_pairs(...)`. Operates only on preserved candidates — no
catalog provider calls.

| Method | Role |
|--------|------|
| `current_item()` / `current_book()` / `current_index()` | What the UI should show |
| `item_count()` / `remaining_count()` / `is_complete()` | Progress |
| `next()` / `previous()` | Navigation (`bool` if moved) |
| `select_candidate(candidate)` / `skip_current()` | Record one decision per slot |
| `finish()` / `is_finished()` | Seal against further edits |
| `decisions()` / `decision_at(i)` / `books()` / `items()` | Inspection |

### `BookReviewService` — Experimental — External

Module: `classroom_library_label_maker.services.book_review_service`

**Purpose:** Apply a **finished** `ReviewSession` to produce updated in-memory
`Book` objects and a `ReviewSessionResult`. Does not write workbooks or call
providers.

| Method | Inputs | Outputs |
|--------|--------|---------|
| `apply(session)` | Finished `ReviewSession` | `ReviewSessionResult` |

Selecting a candidate → new `Book` with ISBN-13 (else ISBN-10); title/author
and other fields preserved. Skipping → original book unchanged.

### `InventoryUpdateService` — Experimental — External

Module: `classroom_library_label_maker.services.inventory_update_service`

**Purpose:** After review, merge applied decisions into post-enrichment books
and write a **new** inventory workbook via `InventoryWorkbookUpdater`. Never
overwrites the original file. Default destination:
`Inventory (Updated ISBNs).xlsx` beside the source (uses `unique_path` on
collision).

| Method | Inputs | Outputs |
|--------|--------|---------|
| `write_updated_inventory(...)` | source path, settings, books, source_rows, session, review result | written `Path` |

Auto-enriched and review-accepted ISBNs are written; missing-placeholder /
skipped rows are left alone. OpenPyxl stays in
`OpenPyxlInventoryWorkbookUpdater`.

### `NullBookEnrichmentProvider` — Experimental — External

**Purpose:** No-op `BookEnrichmentProvider` that returns `SKIPPED` and echoes
existing title/author. Preserves Version 1.0 generation semantics when used
as the default collaborator.

### `GoogleBooksEnrichmentProvider` — Experimental — External

Module: `classroom_library_label_maker.services.lookups.google_books`
(also re-exported from `classroom_library_label_maker.services`)

**Purpose:** Search Google Books for the best title/author match. Implements
`BookEnrichmentProvider`. HTTP and Google JSON stay inside the adapter.

| Method / ctor | Inputs | Outputs |
|---------------|--------|---------|
| `__init__(*, timeout_seconds=10, max_results=10, api_key=None, fetch_json=None)` | Optional timeout, page size, API key, injectable JSON GET | provider |
| `enrich(book)` | `Book` | `BookEnrichmentResult` (`FOUND` / `AMBIGUOUS` / `NOT_FOUND` / `ERROR`) |

**Query order:** `intitle+inauthor` → `intitle` → free-text `title author`
(sequential; no author-only search).

**Notes**

- Does not mutate `Book`.
- Transport failures map to `ERROR` (no leaked exceptions).
- `fetch_json` is for tests / custom transports; production uses urllib.
- Not the default provider; not used by generation / CLI / GUI.

**External use:** Yes when callers explicitly inject it into
`BookEnrichmentService`.

---

## Protocols

Module: `classroom_library_label_maker.services.protocols`

### `BookEnrichmentProvider` — Experimental — External

**Purpose:** Minimal provider-agnostic contract for enriching a `Book`.
Avoids HTTP and catalog-specific types on the interface.

| Method | Inputs | Outputs |
|--------|--------|---------|
| `enrich(book)` | `Book` | `BookEnrichmentResult` (must not mutate `book`) |

**Extension point:** Implement under `services/lookups/` and inject into
`BookEnrichmentService(provider=...)`.

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

**Purpose:** Narrower ISBN-string lookup (`lookup`) and cover download
(`download`) contracts. Prefer `BookEnrichmentProvider` for book enrichment
pipelines.

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
for placement. At save time applies workbook presentation (document properties,
active `Labels 1` sheet). **Does not print.**

### `workbook_presentation` — Stable — External (helpers)

Module: `classroom_library_label_maker.workbooks.workbook_presentation`

**Purpose:** Print-ready presentation helpers used by openpyxl adapters.
Separate from generation orchestration.

| Helper | Role |
|--------|------|
| `apply_workbook_properties(workbook, *, template=None)` | Title, subject, creator |
| `activate_first_label_sheet(workbook)` | Active sheet = first `Labels N` |
| `apply_worksheet_presentation(sheet, template)` | Gridlines, zoom, page setup, margins, print area from `LabelTemplate` |

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
openpyxl worksheets with wrapping title text and worksheet print presentation.
Persisting the workbook is the job of `OpenPyxlWorkbookWriter` /
`WorkbookWriter.save`.

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

**Purpose:** End-to-end orchestration: import inventory → optional ISBN
enrichment → process barcodes → layout labels → save label workbook. Does not
print or display UI. Does not import Google Books types (depends on
`BookEnrichmentService` only).

| Method | Inputs | Outputs / errors |
|--------|--------|------------------|
| `__init__(settings, *, importer=None, enrichment=None, batch_processor=None, layout_service=None, writer=None, progress_reporter=None)` | Settings + optional collaborators / progress hook | service |
| `generate(*, workbook_path=None, output_path=None, progress_reporter=None)` | Optional inventory / output / per-call progress override | `WorkbookGenerationResult`; may raise `ConfigurationError`, `FileSystemError`, `InvalidWorkbookError`, `LabelLayoutError`, `WorkbookGenerationError` |

Default `output_path`: `{project_root}/output/library_labels.xlsx`.

When `settings.lookup_missing_isbns` is True and `enrichment` is omitted, a
default enrichment service is created. Set `lookup_missing_isbns=False` for
Version 1.0 behavior (no enrichment stage).

Optional progress uses Qt-free `GenerationProgressReporter` /
`GenerationProgress` / `GenerationStage` from
`classroom_library_label_maker.progress` (includes `ENRICHING` /
"Looking up missing ISBNs...").

The CLI `generate` command and the desktop GUI (`gui.GuiController`) both
invoke this service as thin adapters — same generation path, no duplicated
engine logic. GUI checkbox **Look up missing ISBNs automatically** maps to
`lookup_missing_isbns`.

---

### `GenerationProgress` / `GenerationStage` / `GenerationProgressReporter` — Stable — External

Module: `classroom_library_label_maker.progress`

**Purpose:** Structured, UI-agnostic progress events for workbook generation.
Consumable by the desktop GUI today and by a future CLI without changing the
engine.

| Symbol | Role |
|--------|------|
| `GenerationStage` | StrEnum milestones (`importing`, `validating`, …) |
| `GenerationProgress` | Frozen event (`stage`, `message`); `for_stage(stage)` |
| `GenerationProgressReporter` | Protocol: `on_progress(progress)` |

---

## Desktop GUI

Package: `classroom_library_label_maker.gui`

Presentation-only. Domain review state stays on `ReviewSession`.

### `ReviewWizardDialog` — Experimental — External

Module: `classroom_library_label_maker.gui.review_wizard`

**Purpose:** Modal wizard after generation when enrichment left review items
with attached books. Renders progress, book details, and candidate cards;
forwards Previous / Next / Skip / candidate clicks / Finish to the session.

**Finish:** seals the session (`finish()`); `GuiController` then calls
`BookReviewService.apply` and, when the save checkbox is checked,
`InventoryUpdateService.write_updated_inventory`. Completion status lists
both the label workbook and the updated inventory when written.

### `GuiController` review hook

After a successful `GenerationWorker.completed` signal, the controller builds
a session via `review_session_from_generation_result`. Empty queues skip the
wizard and continue with the normal completion status line.

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
