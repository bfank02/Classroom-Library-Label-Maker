# Architecture

Architecture for **Classroom Library Label Maker**, with emphasis on the
`barcode_generator` Python component (`classroom_library_label_maker`).

## Overall system

```
┌───────────────────────────────────────────────────────────────┐
│                Classroom Library Label Maker                  │
│                                                               │
│  ┌─────────────┐   JSON / CLI/EXE    ┌──────────────────────┐ │
│  │ excel/      │ ──────────────────► │ barcode_generator/   │ │
│  │ (.xlsm+VBA) │ ◄────────────────── │ Python package / EXE │ │
│  │ (Phase 2)   │   status / paths    └──────────┬───────────┘ │
│  └─────────────┘                                │             │
│                                                 ▼             │
│                                      output/barcodes/*.png    │
│                                      results JSON             │
│                                                 │             │
│  ┌─────────────┐   LabelTemplate +   ┌──────────▼───────────┐ │
│  │ Print       │   WorkbookGeneration│ label_templates/     │ │
│  │ (not yet)   │ ◄── Service (save   │ + WorkbookWriter     │ │
│  └─────────────┘     done; print no) └──────────────────────┘ │
│                                                               │
│  installer/ → ships EXE + workbook     releases/ → artifacts  │
└───────────────────────────────────────────────────────────────┘
```

**Canonical library workflow (Feature 6):**

```
ExcelImportService
        ↓
(optional) BookEnrichmentService   # lookup_missing_isbns
        ↓
BatchProcessingService
        ↓
WorkbookWriter + LabelLayoutService
        ↓
saved label workbook (.xlsx)
```

Orchestrated by `WorkbookGenerationService`. **Printing is not implemented.**
The CLI `generate` command is a thin adapter over `WorkbookGenerationService`
(same canonical runtime as library callers).

## Startup sequence / application lifecycle

```
Inventory workbook / caller
        │
        ▼
       CLI          cli/parser.py  →  argparse + subcommands
        │
        ▼
  Configuration     config.load_application_settings()
        │             VERSION, assets/, output/, logs/, temp/
        ▼
     Logging        logger.setup_logging()  (console + rotating file)
        │
        ▼
     Command        cli/commands.dispatch()
        │             generate | version | validate* | clean* | diagnostics*
        ▼
     Services       generate → WorkbookGenerationService
        │             (Import → Batch → Layout → Save)
        ▼
      Output        output/barcodes/*.png  +  label .xlsx  +  optional results JSON
                    + logs/
```

\* Reserved commands are registered now and return “not implemented” until
feature sprints land.

### Lifecycle notes

1. **Process start** — `__main__` / console script calls `main()`.
2. **Parse** — `parse_args()` selects a command (`generate` by default).
3. **Configure** — settings resolve project paths without hardcoded absolutes.
4. **Log** — handlers attach only after parse (never at import time).
5. **Execute** — command handlers call services; services never own CLI concerns.
6. **Exit** — stable exit codes (`0` success, `1` failure, `2` not implemented,
   `3` completed with per-item errors).

## CLI architecture

```
main.py
  └─ parse_args()          cli/parser.py
  └─ setup_logging()       logger.py
  └─ dispatch()            cli/commands.py
        ├─ run_generate()
        ├─ run_version()
        ├─ run_validate()      (reserved)
        ├─ run_clean()         (reserved)
        └─ run_diagnostics()   (reserved)
```

| Module | Responsibility |
|--------|----------------|
| `cli/parser.py` | Argparse definitions, help text, legacy flag normalization |
| `cli/commands.py` | Command handlers + `COMMAND_HANDLERS` registry |
| `main.py` | Startup orchestration only |

Adding a command later:

1. Add a constant + subparser in `parser.py`
2. Implement `run_<name>()` in `commands.py`
3. Register it in `COMMAND_HANDLERS`

Legacy invocations without a subcommand still work and map to `generate`.

## Exception hierarchy

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

- Defined in `exceptions.py`
- Support an optional underlying `cause` (set as `__cause__`) for logging
- CLI catches `ApplicationError` for clean user-facing failures
- Services raise these for unrecoverable failures; recoverable issues use
  warning objects on result types (`ImportWarning`, `LabelLayoutWarning`)
## Package layout (src-layout)

```
barcode_generator/src/classroom_library_label_maker/
├── main.py              Process entry / startup only
├── __main__.py          python -m entry
├── metadata.py          Product identity (name, version, license, …)
├── exceptions.py        ApplicationError hierarchy
├── config.py            ApplicationSettings, ProjectPaths, VERSION
├── logger.py            Console + RotatingFileHandler
├── models.py            Domain dataclasses / enums
├── constants.py         Runtime defaults / relative path segments
├── cli/
│   ├── parser.py        Argparse + subcommands
│   └── commands.py      Handlers + dispatch registry
├── progress.py          GenerationStage / GenerationProgress / reporter protocol
├── gui/                 Desktop presentation layer (PySide6)
│   ├── __main__.py      python -m classroom_library_label_maker.gui
│   ├── app.py           QApplication bootstrap + event loop
│   ├── main_window.py   Input form (paths, template, Generate)
│   ├── controller.py    Form state actions + start/finish generation
│   ├── review_wizard.py ReviewWizardDialog (thin over ReviewSession)
│   ├── generation_worker.py  QObject worker (service call + progress forward)
│   ├── icons.py         Application icon discovery (placeholder-safe)
│   └── form_state.py    Immutable selections + validation messages
├── services/
│   ├── isbn_validator.py
│   ├── barcode_generation_service.py
│   ├── batch_processing_service.py
│   ├── book_enrichment_service.py    # Enrichment orchestration (null provider default)
│   ├── book_review_service.py        # ReviewSession + BookReviewService
│   ├── inventory_update_service.py   # Updated inventory workbook after review
│   ├── excel_import_service.py
│   ├── label_layout_service.py
│   ├── workbook_generation_service.py
│   ├── barcode_generator.py          # Deprecated CLI helper
│   ├── batch_processor.py            # Deprecated CLI adapter
│   ├── protocols.py                  # BookEnrichmentProvider + progress / lookup hooks
│   ├── lookups/         GoogleBooksEnrichmentProvider (+ future catalogs)
│   └── covers/          Future cover downloads
├── rendering/           Barcode image rendering (library-agnostic)
│   ├── renderer.py      BarcodeRenderer protocol
│   └── barcode_renderer.py  PythonBarcodeRenderer (EAN-13 PNG)
├── workbooks/           Spreadsheet / workbook I/O (library-agnostic)
│   ├── workbook_reader.py              WorkbookReader protocol
│   ├── openpyxl_workbook_reader.py     OpenPyxlWorkbookReader
│   ├── workbook_writer.py              WorkbookWriter protocol
│   ├── openpyxl_workbook_writer.py     OpenPyxlWorkbookWriter
│   ├── inventory_workbook_updater.py   InventoryWorkbookUpdater protocol
│   ├── openpyxl_inventory_workbook_updater.py  ISBN save-as updates
│   ├── workbook_presentation.py        Print-ready view / page setup
│   ├── label_sheet_target.py           LabelSheetTarget + LabelPlacement
│   ├── in_memory_label_sheet_target.py InMemoryLabelSheetTarget
│   ├── in_memory_workbook_writer.py    InMemoryWorkbookWriter
│   └── openpyxl_label_sheet_target.py  OpenPyxlLabelSheetTarget
├── label_templates/     Physical label-sheet specs (inches, immutable)
│   ├── label_template.py            LabelTemplate protocol + LabelTemplateSpec
│   ├── avery_5160.py                Avery 5160 layout data
│   └── template_registry.py         TemplateRegistry
└── utils/
    └── file_utils.py
```

Import style (absolute, package-qualified):

```python
from classroom_library_label_maker.services import BatchProcessingService
from classroom_library_label_maker.config import load_application_settings
from classroom_library_label_maker.exceptions import InvalidISBNError
```

Root package `__init__` exports a narrow public API (models + exceptions +
`__version__`). Prefer submodule imports in library-style call sites.

## Package responsibilities

| Area | Responsibility |
|------|----------------|
| `main` | Startup: parse → configure → log → dispatch |
| `cli` | CLI parsing and command handlers |
| `progress` | Qt-free generation stage events for GUI/CLI adapters |
| `gui` | Desktop presentation (PySide6); thin adapter only |
| `gui.generation_worker` | Background `QObject` that runs the generation service |
| `gui.review_wizard` | `ReviewWizardDialog` over `ReviewSession` |
| `gui.form_state` | Immutable GUI selections + field validation messages |
| `metadata` | Single source of truth for product identity |
| `models` | Domain dataclasses and `BarcodeStatus` enum |
| `exceptions` | Typed application errors |
| `config` | Project root, VERSION, asset/runtime paths |
| `logger` | Production logging setup (no import-time side effects) |
| `services.*` | Validation, generation, batch, enrichment, import, layout, workbook generation |
| `services.protocols` | Extension contracts for enrichment / lookups / covers / progress |
| `rendering` | Library-agnostic barcode image rendering |
| `workbooks` | Library-agnostic spreadsheet read / label-sheet write |
| `label_templates` | Immutable physical label-sheet specifications |
| `utils.file_utils` | JSON + directory helpers |
| `constants` | Operational defaults (paths, log sizes) — not product branding |

## ISBN validator (`services/isbn_validator.py`)

`IsbnValidator` (alias `ISBNValidator`) is a **stateless** normalizer/validator.
It never raises for expected ISBN failures; it always returns
`ValidationResult`.

### Stable public API (frozen)

The following methods are the **stable public interface** for ISBN validation.
They are considered feature-complete and **must remain backward compatible**
unless a **major** version bump intentionally breaks them:

| Method | Contract |
|--------|----------|
| `normalize(isbn: str \| None) -> str` | Clean an ISBN string (trim; remove spaces/hyphens). Does **not** validate. |
| `validate(isbn: str \| None) -> ValidationResult` | Validate one ISBN; always returns a result (never raises for invalid input). |
| `validate_many(isbns: Iterable[str \| None]) -> list[ValidationResult]` | Validate many values by calling `validate()` per item, preserving order. |

Additional public helpers (`is_valid`, `compute_check_digit`) exist for
convenience but are not part of the frozen compatibility surface above.

Validation order: empty → numeric → length 13 → prefix `978`/`979` → checksum.

`ValidationErrorCode` is the single source of truth for failure **codes and
default user-facing messages** (`error_code.message`). `ValidationResult.errors`
is populated from that message.

### Performance benchmarks

Engineering timings live under `barcode_generator/tests/benchmarks/`. They are
manual developer tools — **not** part of the normal unit-test suite and must
**never** fail CI. See the barcode generator README for how to run them.

* `benchmark_isbn_validator.py` — ISBN normalize/validate throughput
* `benchmark_google_books_enrichment.py` — Teacher Demo Library enrichment
  (requests, cache, 429s, wall time; optional `GOOGLE_BOOKS_API_KEY`)

## Rendering layer (`rendering/`)

Barcode **image encoding** is isolated from business logic so the generation
service can orchestrate skip rules and results without depending on a specific
barcode library.

```
Application (CLI / Excel / library callers)
        ↓
BarcodeGenerationService  (services/barcode_generation_service.py)
        ↓
BarcodeRenderer             (rendering/renderer.py — protocol)
        ↓
PythonBarcodeRenderer       (rendering/barcode_renderer.py)
        ↓
Third-party barcode library (python-barcode + Pillow)
```

**Why isolate rendering?**

* Keeps vendor types (python-barcode, Pillow, etc.) out of services and CLI
* Allows swapping backends without rewriting batch orchestration
* Makes testing the service possible with a fake/mock renderer

**Public API**

* `BarcodeRenderer` — protocol: `render_to_file(data, output_path, *, symbology) -> Path`
* `BarcodeSymbology` — `EAN13` (implemented), plus reserved `CODE128` / `QR`
* `PythonBarcodeRenderer` — EAN-13 PNG backend via python-barcode + Pillow

### Renderer configuration (`ApplicationSettings`)

Renderer geometry lives on `ApplicationSettings` (defaults in `constants.py`):

| Setting | Default | Meaning |
|---------|---------|---------|
| `barcode_module_width` | `0.33` mm | EAN-13 SC2 module width |
| `barcode_module_height` | `15.0` mm | Bar height |
| `barcode_quiet_zone` | `6.5` mm | Quiet-zone margin |
| `barcode_font_size` | `10` | Human-readable text size (pt) |
| `barcode_dpi` | `300` | PNG resolution |

`BarcodeGenerationService` builds `PythonBarcodeRenderer.from_settings(settings)`
so call sites never hardcode writer options. Changing these values changes
rendered output; update golden references and re-run manual scan verification
after intentional tweaks.

### Barcode generation service (`services/barcode_generation_service.py`)

`BarcodeGenerationService` is the reusable engine for creating barcode images.
It accepts a validated `Book`, resolves paths from `ApplicationSettings`, skips
existing files (`ALREADY_EXISTS`), and delegates encoding to a `BarcodeRenderer`.

It does **not** re-validate ISBNs and does **not** import third-party barcode
libraries.

### Batch processing service (`services/batch_processing_service.py`)

`BatchProcessingService` is the **canonical** orchestration layer for
collections of `Book` objects. `ExcelImportService` feeds books into this
service; `LabelLayoutService` consumes barcode paths afterward.

**Orchestration responsibilities**

* Validate each book with `IsbnValidator` (Feature 1)
* Generate barcodes for valid books with `BarcodeGenerationService` (Feature 2)
* Continue after per-book validation or generation failures
* Return `BatchProcessingResult` with counts, `elapsed_seconds`, and derived
  `books_per_second`
* Preserve **input order** in `results` (`BookProcessingResult` index `i`
  always corresponds to input book `i`)

**Progress reporting**

Optional `BatchProgressReporter` hooks (`on_batch_started`,
`on_book_processed`, `on_batch_completed`) allow future CLI/UI progress
without changing `process_books()`. No UI is implemented here.

**Future cancellation support**

Optional `BatchCancellationToken` (`is_cancellation_requested`) is accepted on
the constructor so UI can plug in later **without changing the public API**.
Cancellation is **not enforced** in this release; the token is retained only
as a stable extension point.

**Metrics**

`BatchProcessingResult.books_per_second` is derived as
`total_processed / elapsed_seconds` (returns `0.0` when elapsed time is zero).
It is not stored separately.

### Book enrichment service (`services/book_enrichment_service.py`)

`BookEnrichmentService` is the orchestration layer for automatic ISBN / catalog
metadata enrichment. It depends **only** on the `BookEnrichmentProvider`
protocol and never imports HTTP clients or catalog SDKs.

```
BookEnrichmentService
        │  enrich(book) / enrich_many(books)
        │  in-memory cache (normalized title + author)
        ▼
BookEnrichmentProvider   (protocol)
        │
        ├─ NullBookEnrichmentProvider          (explicit no-op)
        └─ GoogleBooksEnrichmentProvider       (default when lookup enabled)
```

`WorkbookGenerationService` constructs enrichment via
`create_default_enrichment_service(api_key=settings.google_books_api_key)` when
`lookup_missing_isbns` is True,
or accepts an injected `BookEnrichmentService` for tests.
**Phase 3 behavior (integrated enrichment)**

* `lookup_missing_isbns` (default **True**) gates the enrichment stage.
* When enabled, `WorkbookGenerationService` depends only on
  `BookEnrichmentService` (default factory uses Google Books internally —
  the orchestrator never imports catalog SDKs).
* Progress stage `ENRICHING` reports **"Looking up missing ISBNs..."**, then
  updates with **"(n of total)"** as each missing-ISBN book is looked up.
* Books with blank ISBN cells are imported with a provisional placeholder
  when lookup is enabled, enriched by title/author, then validated as usual.
* Ambiguous / not-found / error outcomes become warnings; generation continues.
* `EnrichmentSummary` on `WorkbookGenerationResult` records counts (already
  had ISBN, looked up, found, ambiguous, not found, errors, cache hits/misses)
  plus `review_items` (`ReviewItem` title/author/status/message, optional
  `candidates`) for books that still need attention. GUI and CLI show an
  **ISBN Lookup Summary** with up to five review titles when needed.
* When `lookup_missing_isbns` is **False**, import skips blank ISBN rows and
  no enrichment stage runs (Version 1.0 behavior).
* The teacher's inventory workbook is never modified.

**Candidate preservation (Phase 4.1 — future interactive review)**

Automatic enrichment already produces `AMBIGUOUS` / `NOT_FOUND` / `ERROR`
outcomes. Phase 4.1 preserves catalog choices on those results so a later
review UI can let teachers pick an ISBN **without additional Google Books
requests**:

* Immutable `ReviewCandidate` holds `isbn13`, `isbn10`, `title`, `author`,
  `publisher`, `published_date`, and internal `confidence_score`. Presentation
  uses derived `confidence_label` (`Very High` / `High` / `Medium` / `Low`)
  from domain thresholds — GUI/CLI must not reinterpret the numeric score.
* `BookEnrichmentResult.candidates` is populated for `AMBIGUOUS` (ordered by
  descending confidence). Successful `FOUND` lookups keep `candidates=()`.
* `ReviewItem.candidates` carries the same tuple through
  `EnrichmentSummary` for the generation result.
* The in-memory enrichment cache stores the full result (including
  candidates), so repeat title/author lookups reuse preserved peers.

No review dialog is built in this phase; generation behavior is unchanged
aside from attaching candidate data on review items.

**Confidence presentation (domain layer)**

Match selection still uses numeric scores inside providers. For teacher-facing
copy, `ReviewCandidate.confidence_score` is the internal `[0, 1]` value and
`ReviewCandidate.confidence_label` (via `confidence_label_for_score`) maps it
to `Very High` / `High` / `Medium` / `Low` using module thresholds
(`CONFIDENCE_LABEL_VERY_HIGH` ≥ 0.90, `HIGH` ≥ 0.80, `MEDIUM` ≥ 0.70).
Adapters should show `"{confidence_label} Match"` and must not duplicate
threshold logic in Qt, CLI, or formatting helpers.

**Interactive review workflow (Phase 4.2 — business layer only)**

After enrichment, teachers can resolve ambiguous matches without further
catalog requests. The workflow is fully UI-independent:

```
GUI (ReviewWizardDialog)  →  ReviewSession  →  BookReviewService  →  updated Book objects
```

* `ReviewSession` owns queue state: current item/book, navigation
  (`next` / `previous`), teacher decisions, remaining/completion, and
  `finish()` to seal the session. Construct from parallel `Book` +
  `ReviewItem` pairs (or `ReviewSession.from_pairs`). The GUI must not
  keep its own indexes.
* Immutable `ReviewDecision` records exactly one action per queue entry:
  select a preserved `ReviewCandidate`, or `skipped=True`.
* `BookReviewService.apply(finished_session)` produces
  `ReviewSessionResult` (`updated_books`, resolved/skipped/unresolved/
  total_reviewed). Selecting a candidate creates a **new** `Book` with
  the chosen ISBN (ISBN-13 preferred) and preserves title, author, and
  other fields. Skipping leaves the original book unchanged.
* No workbook writes, no Google Books / provider calls, no Qt types.
  Generation (`WorkbookGenerationService`) attaches the original `Book` on
  each `ReviewItem` so the GUI can seed a session without re-querying.

**Interactive review wizard (Phase 4.3 — GUI presentation)**

```
GenerationWorker.completed
        │
        ▼
GuiController._on_generation_completed
        │  if review items with books →
        ▼
ReviewWizardDialog  (Qt)  ──actions──►  ReviewSession  (domain)
        │ Finish
        ▼
BookReviewService.apply(finished session)
        │
        ▼
existing completion status (ISBN Lookup Summary, etc.)
```

* `ReviewWizardDialog` shows progress (`Book X of Y` + bar), book title/
  author/reason, selectable candidate cards (`"{confidence_label} Match"`,
  ISBN, title, author, publisher · year), and a **Recommended** badge on the
  highest-confidence card.
* Buttons call `ReviewSession` (`previous` / `next` / `skip_current` /
  `select_candidate` / `finish`). Qt does not own the review index.
* Single **Very High** candidate is pre-selected (teacher may still Skip).
* Checkbox **Save updated inventory workbook when review is complete**
  (default on) is persisted in `GuiPreferences`. When checked on Finish,
  `InventoryUpdateService` writes a new workbook
  (`Inventory (Updated ISBNs).xlsx`, unique suffix on collision) beside the
  original — never overwriting the teacher's file. Auto-enriched and
  review-accepted ISBNs are written; skipped rows stay unchanged.
* Completion status includes a **Generation Complete** block listing the
  label workbook and updated inventory when written.
* No review items → wizard is skipped; success flow unchanged.

**Inventory workbook update (Phase 4.4)**

```
ReviewSession + BookReviewService
        │ merged books (import order)
        ▼
InventoryUpdateService
        │
        ▼
InventoryWorkbookUpdater (OpenPyxlInventoryWorkbookUpdater)
        │ save-as copy
        ▼
Inventory (Updated ISBNs).xlsx
```

* `WorkbookGenerationResult.books` / `source_rows` carry post-enrichment books
  and Excel row numbers so the updater can patch ISBN cells without
  re-importing or changing generation behavior.
* OpenPyxl stays in the workbook adapter; the service only builds update
  pairs and chooses a unique destination path (`utils.file_utils.unique_path`).

**In-memory enrichment cache**




`BookEnrichmentService` keeps a process-local dict of
`BookEnrichmentResult` values for the lifetime of the service instance.
There is no persistent storage; destroying the service discards the cache.

* **Why on the service, not providers:** caching is an orchestration concern.
  Providers stay focused on lookups. One cache covers every
  `BookEnrichmentProvider` (null, Google Books, future Open Library, …)
  without duplicated logic or provider-specific HTTP caches.
* **Cache key:** `(normalize_catalog_text(title), normalize_catalog_text(author))`
  via shared `services/enrichment_normalize.py` (same rules as Google Books
  matching). ISBN is **not** part of the key so rows missing ISBNs still
  share a lookup for the same work.
* **Behavior:** on hit, return the cached result immediately (no provider
  call; `Book` unchanged). On miss, call the provider, store the result,
  return it. **All** statuses are cached (`FOUND`, `NOT_FOUND`,
  `AMBIGUOUS`, `ERROR`, `SKIPPED`) to avoid repeat work for failures too.
* **Diagnostics:** `cache_hits`, `cache_misses`, and `cache_size` are
  available for tests/logging only — not user-facing.

### Google Books provider (`services/lookups/google_books.py`)

`GoogleBooksEnrichmentProvider` keeps HTTP and Google JSON types inside the
adapter. Callers only see `BookEnrichmentResult`.

**Query strategy (sequential; no author-only searches)**

1. `<title> inauthor:<surname>`
2. `<title> <author>`
3. `<title>`

Stops early on `FOUND` or `AMBIGUOUS`. Empty results fall through to the next
query. Transport failures become `ERROR` (timeouts, HTTP errors, malformed
JSON) — exceptions are not leaked.

**Normalization**

Titles and authors are compared after casefolding, stripping punctuation, and
collapsing whitespace (so `Charlotte's Web` matches `Charlottes Web`).

**Confidence scoring**

Each candidate is scored with weighted title/author similarity
(`0.65 * title + 0.35 * author` via `difflib` + token overlap). Selection:

* `FOUND` — single confident match, or multiple editions of the same work
  (prefer ISBN-13); `candidates` left empty
* `AMBIGUOUS` — multiple distinct works with close high scores; peer list
  stored on `candidates` (descending confidence) for later review
* `NOT_FOUND` — no candidate above the confidence floor
* `ERROR` — network / parse failures

**Result mapping**

Populates `isbn` (ISBN-13 preferred), `title`, `author`, and `metadata`
(`isbn13`, `isbn10`, `authors`, `normalized_title`, `confidence`,
`google_volume_id`, `provider=google_books`, …). On `AMBIGUOUS`, also maps
scored peers to public `ReviewCandidate` values. Never mutates the input
`Book`.

**Authentication & rate limiting**

Configuration resolves the API key **once** in
`config.load_google_books_auth_config()` (the only place the key is read):

1. ``GOOGLE_BOOKS_API_KEY`` environment variable (when present)
2. Per-user file ``google_books_api_key.txt`` under Application Support /
   LOCALAPPDATA (for packaged apps that do not inherit shell exports)
3. Anonymous mode

Result is stored on `ApplicationSettings` (`google_books_api_key`,
`google_books_auth_status`). Startup logs exactly one of:

* `Google Books authentication: Enabled`
* `Google Books authentication: Disabled (anonymous mode)`
* `Google Books authentication: Disabled (invalid API key configuration)`

No network “test” request is made at startup. The key is injected into
`GoogleBooksEnrichmentProvider(api_key=...)` via
`create_default_enrichment_service(api_key=settings.google_books_api_key)`;
the provider never reads the environment.

Live HTTP pacing defaults:

* **Authenticated** ≈ 0.40s between requests
* **Anonymous** ≈ 1.25s between requests

HTTP **429** responses still use capped exponential backoff (up to 6 retries,
max ~65s, honoring `Retry-After`), adaptive slowdown, and a circuit breaker.
HTTP **401/403** drop the key for the remainder of the run and retry once in
anonymous mode (invalid keys are not retried repeatedly). Rate-limit and auth
failures are not queued in the review wizard. Injectable `fetch_json` bypasses
pacing for unit tests.

Never log API keys or URLs that contain them. Production builds should obtain
the key from environment/configuration — never embed it in source or packages.

**Testing**

Inject `fetch_json=` to supply canned payloads; unit tests do not require
Internet access.

**Adding another catalog provider**

1. Implement `BookEnrichmentProvider.enrich(book) -> BookEnrichmentResult`
   under `services/lookups/` (keep HTTP details inside the adapter).
2. Inject it: `BookEnrichmentService(provider=MyProvider(...))` (or change
   `create_default_enrichment_service()`).
3. For ambiguous outcomes, populate `BookEnrichmentResult.candidates` so
   interactive review can reuse peers without a second catalog round-trip.

`IsbnLookupService` remains a narrower ISBN-string lookup protocol; prefer
`BookEnrichmentProvider` for new enrichment work.

### Deprecated modules (unused by CLI)

`BatchProcessor`, `BarcodeGenerator`, and `BatchResults` remain in the package
for transitional imports only. The CLI **does not** call them. Prefer
`WorkbookGenerationService` / `BatchProcessingService` /
`BarcodeGenerationService`. These stubs may be removed in a later cleanup.
### Manual barcode verification

Generated PNGs should scan back to the normalized ISBN-13 (13 digits, no
hyphens). Example: `978-0-06-440055-8` → scan result **`9780064400558`**.

Full phone / hardware scanner checklist:
[`docs/Barcode Scan Verification.md`](Barcode%20Scan%20Verification.md).

### Golden barcode tests

`barcode_generator/tests/golden/` holds optional known-good reference PNGs and
comparison helpers. Philosophy:

* Catch accidental visual regressions when rendering settings or dependencies
  change
* Prefer structural + perceptual (average-hash) checks — **not** byte-identical
  PNG equality
* Skip (do not fail CI) when a reference file is absent
* Refresh references only after intentional rendering changes; see
  `tests/golden/README.md` and set `UPDATE_GOLDEN=1` to rewrite goldens

### Future renderer extension points

Additional backends can implement `BarcodeRenderer` without changing callers:

| Future renderer | Intent |
|-----------------|--------|
| SVG renderer | Vector barcodes for print pipelines |
| QR code renderer | Alternate symbology via `BarcodeSymbology.QR` |
| Code128 renderer | Non-ISBN linear codes via `BarcodeSymbology.CODE128` |
| Alternate libraries | Drop-in replacements for python-barcode |

Do not implement these until a feature sprint requires them.

## Workbook layer (`workbooks/`)

Spreadsheet **I/O** is isolated from import orchestration, label layout, and
domain mapping so services never depend on openpyxl (or any other vendor)
directly.

```
Application
    ↓
ExcelImportService          (services/excel_import_service.py)
    ↓
WorkbookReader              (workbooks/workbook_reader.py — protocol)
    ↓
OpenPyxlWorkbookReader      (workbooks/openpyxl_workbook_reader.py)
    ↓
openpyxl
```

```
Application
    ↓
LabelLayoutService          (services/label_layout_service.py)
    ↓
LabelSheetTarget            (workbooks/label_sheet_target.py — protocol)
    ↓
OpenPyxlLabelSheetTarget / InMemoryLabelSheetTarget
    ↓
openpyxl (placement cells / images)
```

```
Application
    ↓
WorkbookGenerationService   (services/workbook_generation_service.py)
    ↓
WorkbookWriter              (workbooks/workbook_writer.py — protocol)
    ↓
OpenPyxlWorkbookWriter      (owns OpenPyxlLabelSheetTarget + save)
    ↓
openpyxl
```

**Why isolate Excel-specific code?**

* Keeps openpyxl types (workbooks, worksheets, cells) out of services and CLI
* Allows swapping backends without rewriting import / layout / generation
* Makes testing possible with fake readers / `InMemoryWorkbookWriter`
* Mirrors the `BarcodeRenderer` pattern used for barcode image encoding

**Public API**

* `WorkbookReader` — protocol: `open`, `close`, `sheet_names`, `iter_rows`
* `OpenPyxlWorkbookReader` — openpyxl backend (plain string cells only)
* `WorkbookWriter` — protocol: `create_workbook`, `get_label_sheet_target`,
  `save`, `close`
* `OpenPyxlWorkbookWriter` — create/save adapter (default for generation);
  applies workbook presentation at save
* `InMemoryWorkbookWriter` — test writer
* `LabelSheetTarget` — protocol: `begin_page`, `place_label`
* `LabelPlacement` — immutable placement payload (title, author, ISBN, barcode)
* `InMemoryLabelSheetTarget` — records pages/placements for tests
* `OpenPyxlLabelSheetTarget` — openpyxl placement + worksheet presentation
* `workbook_presentation` — helpers for document properties, page setup,
  print area, gridlines, zoom (print-ready; does not print)

`iter_rows` yields plain `(str | None, ...)` tuples only — never vendor cell
objects. Mapping those rows into `Book` instances is the job of
`ExcelImportService`. Layout writes go through `LabelPlacement` only.
Workbook persistence goes through `WorkbookWriter.save` only.

### Workbook presentation (print readiness)

Presentation is **separate from** `WorkbookGenerationService` orchestration.
It lives in the workbook adapters / `workbook_presentation` helpers so a
teacher can open the saved `.xlsx` and use Excel Print without manual setup.

**Workbook-level (at save):** title/subject/creator (from `metadata`), active
sheet set to the first `Labels N` worksheet.

**Worksheet-level (at `begin_page`):** hide gridlines, zoom 100%, orientation /
paper size / margins from `LabelTemplate`, print area covering the label grid,
fit-to-page width, horizontal centering for print.

**Label cells:** centered Calibri text; titles wrap (`wrap_text=True`) so long
titles do not spill into neighboring labels. Layout geometry is unchanged.

### Excel import service (`services/excel_import_service.py`)

`ExcelImportService` imports books from a configured workbook/worksheet using
column header names from `ApplicationSettings`. It:

* Maps populated rows to `Book` (ISBN, Title, Author, Copies)
* Preserves worksheet row numbers in `ImportResult.source_rows`
* Skips blank rows; records `ImportWarning` for recoverable row issues
* Continues after malformed rows
* Raises `FileSystemError` / `InvalidWorkbookError` / `ConfigurationError`
  for unrecoverable failures

It does **not** validate ISBNs, generate barcodes, or run batch processing.

`ImportResult` and `ImportWarning` are immutable value objects (`frozen=True`).

### Workbook template versioning (extension point)

Workbook template versioning is **not enforced** yet. The architecture can
accommodate multiple template versions without changing `WorkbookReader`:

**Where version metadata could live (pick one when implementing):**

* A dedicated cell (e.g. `Meta!B2` or `Books!Z1` labeled `TemplateVersion`)
* A `Meta` / `About` worksheet with a `Version` row
* Excel custom document properties (`openpyxl` workbook properties)
* Filename / companion manifest (less preferred for teacher workbooks)

**Where compatibility checks would run:**

In `ExcelImportService.import_books`, **after** the workbook is opened and the
target worksheet is confirmed, and **before** header/column resolution and row
mapping (marked in code). A mismatch would raise `InvalidWorkbookError` (or a
future more specific subtype) without partial imports.

**Supporting multiple versions later:**

* `ApplicationSettings` can grow an expected `workbook_template_version`
* Column maps / sheet names can be selected per version
* Older templates can keep a dedicated mapper path while newer ones evolve

Do not implement version validation until a template contract is published.

### Future workbook reader extension points

Additional backends can implement `WorkbookReader` without changing callers:

| Future reader | Intent |
|---------------|--------|
| `CSVWorkbookReader` | Plain CSV / TSV classroom exports |
| `GoogleSheetsReader` | Remote Google Sheets via API |
| `OneDriveWorkbookReader` | Workbooks stored in OneDrive / SharePoint |
| `LibreOfficeWorkbookReader` | ODS / LibreOffice-centric pipelines |

Do not implement these until a feature sprint requires them.

## Label templates (`label_templates/`)

Physical **label-sheet geometry** is isolated from layout placement, Excel
worksheets, and printing. Templates are immutable value objects measured in
**inches only** — never pixels, points, printer dots, or Excel row/column units.

```
ApplicationSettings.label_template_id
        │
        ▼
TemplateRegistry
        │
        ▼
LabelTemplate / AVERY_5160
        │
        ▼
LabelLayoutService
        │
        ▼
LabelSheetTarget
```

**Why separate layout data from rendering?**

* `LabelLayoutService` places labels using inches from `LabelTemplate` without
  knowing Avery vs Brother vs custom vendors
* Worksheet adapters convert inches → Excel column/row units at the edge
* New templates register in `TemplateRegistry` without modifying the layout
  service

**Public API**

* `LabelTemplate` — protocol for physical sheet specs
* `LabelTemplateSpec` — frozen dataclass implementation
* `TemplateRegistry` / `create_default_template_registry()`
* `AVERY_5160` (`template_id`: `avery-5160`) — built-in Avery 5160 data

`ApplicationSettings.label_template_id` defaults to `avery-5160` and is the
**single source of truth** for which template `LabelLayoutService` uses.
`ApplicationSettings.default_label_type` is a deprecated compatibility field
(legacy underscore id) and is **not** read by the layout service.
### Label layout service (`services/label_layout_service.py`)

`LabelLayoutService` arranges already-imported `Book` objects onto worksheet
pages using the selected `LabelTemplate` and a `LabelSheetTarget`:

* Calculates grid positions from `template.rows` / `template.columns`
* Paginates when a page is full (never silently discards labels)
* Places title, author, ISBN, and barcode image (or placeholder)
* Returns immutable `LabelLayoutResult` with pages/labels/empty-slot stats,
  timing, and warnings
* Raises `ConfigurationError` for unknown templates and `LabelLayoutError`
  for unrecoverable layout failures

It does **not** generate barcodes, validate ISBNs, import workbooks, print,
save workbooks, or display UI. Optional `barcode_paths` map ISBN → PNG;
missing files become placeholders with warnings.

### Workbook generation service (`services/workbook_generation_service.py`)

`WorkbookGenerationService` is the end-to-end orchestrator:

1. `ExcelImportService.import_books`
2. Optional `BookEnrichmentService` (when `lookup_missing_isbns`)
3. `BatchProcessingService.process_books` (validate + generate/reuse barcodes)
4. `WorkbookWriter.create_workbook`
5. `LabelLayoutService.layout_books` on `writer.get_label_sheet_target()`
6. `WorkbookWriter.save`

Returns immutable `WorkbookGenerationResult` (including `EnrichmentSummary`).
Does **not** print or show UI. Default output path:
`{project_root}/output/library_labels.xlsx`.

### Future label template extension points

| Future template | Intent |
|-----------------|--------|
| Avery 5163 | Larger shipping / barcode labels |
| Avery 8160 | Same geometry as 5160 (Easy Peel variant) |
| Avery 5260 | Compatible 5160-geometry product line |
| A4-compatible templates | Metric page size / regional products |
| Brother label sheets | Brother-branded sheet geometries |
| Custom user-defined templates | Teacher-specific or district templates |

Register new `LabelTemplateSpec` instances; do not change `LabelLayoutService`.

## Application metadata (`metadata.py`)

Product-facing strings are centralized so installers, CLI help, logs, and
about dialogs cannot drift apart:

* `APP_NAME`, `APP_DESCRIPTION`, `APP_AUTHOR`, `APP_COMPANY`
* `APP_COPYRIGHT`, `APP_VERSION`, `APP_WEBSITE`, `APP_LICENSE`
* Technical IDs: `APP_PACKAGE_NAME`, `APP_DISTRIBUTION_NAME`, `APP_CLI_NAME`

**Why centralize?** Hardcoded product strings in CLI parsers, log lines, and
build scripts become inconsistent as the app grows (Excel, installer, updates).
One module is the contract for branding and version identity.

**Version tradeoff:** `APP_VERSION` is a static constant synchronized with the
root `VERSION` file (and mirrored by setuptools `dynamic = ["version"]`).
Import-time reads of `VERSION` were avoided because wheel installs may not
ship that file beside the package and path discovery would couple metadata to
`config`. At runtime, `read_version()` still prefers the on-disk `VERSION`
when the project tree is present and falls back to `APP_VERSION`.

## Data flow (canonical library pipeline)

```
Inventory Excel workbook
    │
    ▼
WorkbookGenerationService.generate()
    │
    ├─ ExcelImportService.import_books()
    ├─ BookEnrichmentService (optional; lookup_missing_isbns)
    ├─ BatchProcessingService.process_books()
    │     ├─ IsbnValidator
    │     └─ BarcodeGenerationService
    ├─ WorkbookWriter.create_workbook()
    ├─ LabelLayoutService.layout_books(target=writer.get_label_sheet_target())
    └─ WorkbookWriter.save(output_path)
    │
    ▼
WorkbookGenerationResult (+ EnrichmentSummary)  +  output/*.xlsx  +  barcodes
logs/application.log (rotating)
```

**Implemented today:** import, optional missing-ISBN enrichment, validation,
barcode generation, batch orchestration, label layout, label workbook
**save**, CLI `generate` and desktop GUI via `WorkbookGenerationService`
(`python -m classroom_library_label_maker.gui`). GUI generation runs on a
Qt worker thread with stage progress (including ISBN lookup).

**Not implemented:** GUI cancellation, **printing** / print preview, Excel VBA
UI (Phase 2). CLI does not yet print progress events (hooks are ready).

### Desktop GUI launch

```
python -m classroom_library_label_maker.gui
    → classroom_library_label_maker.gui:main
        → create QApplication
        → MainWindow + GuiController
        → event loop

label-maker-gui   # same entry point after pip install
```

### Desktop GUI workflow (RC3.5 — polished)

```
MainWindow
  Generate Labels
      → GuiController validates + build_application_settings()
      → GenerationJob (immutable inputs)
      → QThread + GenerationWorker.run()
            → WorkbookGenerationService.generate(progress_reporter=…)
                → GenerationProgress (stage + message)
            → emit progress / completed(result) | failed(exc)
      → GuiController updates status label
```

UX notes:

* Window title is the product name; Esc closes the window
* Save dialog defaults to `Documents/library_labels.xlsx` and applies/preserves
  Excel extensions; inventory browse prefers the sample workbook folder when
  present
* Terminology: **inventory workbook** (input) and **label workbook** (output)
* Status wording is concise and actionable (no Python tracebacks)
* Completed runs use three presentation states from
  `WorkbookGenerationResult.completion_state`: clean success, success with
  warnings (review before printing), or failure via exception. Warning details
  stay on `result.warnings` for CLI listing / a future details UI; the status
  line shows only a count + review guidance
* Application icon loads from `assets/icons/` when a non-empty file is present
* Teacher quick start: `docs/Quick Start.md`; sample inventory:
  `samples/Sample Books.xlsx`

Progress originates in the engine (`progress.GenerationStage` /
`GenerationProgress` / `GenerationProgressReporter`). The worker only forwards
events; the controller only displays them. `WorkbookGenerationService` remains
Qt-unaware and can feed a future CLI progress consumer without API redesign.

Stages (significant transitions only):

* Importing workbook...
* Validating books...
* Generating barcodes...
* Creating labels...
* Saving workbook...

While a job is running, Browse / template / Generate are disabled and
duplicate Generate requests are ignored.

### CLI `generate` (canonical runtime)

```
CLI generate
    → WorkbookGenerationService.generate()
        → ExcelImportService / BatchProcessingService / LabelLayoutService
        → WorkbookWriter.save
    → console summary from WorkbookGenerationResult
    → optional --results JSON (result.to_dict)
```

Exit codes: `0` success, `1` invalid arguments, `2` import failure,
`3` generation failure, `4` unexpected internal error, `5` reserved command
not implemented.

`ExcelImportService` only produces `Book` + `ImportResult`. Validation,
barcode generation, layout, and save remain separate collaborators coordinated
by `WorkbookGenerationService`.
## Folder purposes

| Path | Tracked? | Purpose |
|------|----------|---------|
| `src/classroom_library_label_maker/` | Yes | Installable Python package |
| `tests/` | Yes | Unit tests |
| `tests/integration/` | Yes | End-to-end real-adapter tests |
| `tests/golden/` | Yes | Optional golden barcode PNGs + helpers |
| `tests/assets/workbooks/` | Yes | Sample `.xlsx` files for Excel import tests |
| `assets/icons/` | Yes | EXE icon + logo placeholders |
| `assets/templates/` | Yes | Reserved folder (geometry lives in `label_templates/`) |
| `assets/sample-data/` | Yes | Example JSON payloads |
| `assets/resources/` | Yes | Misc static resources |
| `output/barcodes/` | Structure only | Generated PNGs |
| `logs/` + `logs/archive/` | Structure only | App log + rotated backups |
| `temp/` | Structure only | Scratch workspace |
| `VERSION` | Yes | SemVer for this component |

## Future extension points

1. **Desktop GUI cancellation** — cooperative cancel (keep
   `WorkbookGenerationService` unaware of Qt)
2. **CLI progress output** — consume `GenerationProgressReporter` without
   changing the generation pipeline
3. **CLI commands** — `validate`, `clean`, `diagnostics` already registered
4. **ISBN / catalog enrichment** — wired into generation when
   `lookup_missing_isbns` is True (`BookEnrichmentService` +
   `GoogleBooksEnrichmentProvider` by default). Additional providers can
   still be injected under `services/lookups/`.
5. **Cover downloads** — `CoverDownloadService` under `services/covers/`
6. **Rendering backends** — additional `BarcodeRenderer` implementations under
   `rendering/` (SVG, QR, Code128, alternate libraries)
7. **Workbook readers** — additional `WorkbookReader` implementations under
   `workbooks/` (CSV, Google Sheets, OneDrive, LibreOffice)
8. **Inventory / checkout / reading levels** — extend `Book` optional fields
9. **Label templates** — additional `LabelTemplateSpec` entries (5163, 8160,
   A4, Brother, custom) via `TemplateRegistry`
10. **Print / print preview** — print the saved label workbook
11. **Additional label templates** — register more `LabelTemplateSpec` ids;
   configure via `label_template_id`
12. **Auto-update / installer** — `installer/` + `releases/` driven by `VERSION`
13. **Remove deprecated stubs** — `BatchProcessor` / `BarcodeGenerator` /
    `BatchResults` once no transitional imports remain

## Coding standards

- Python 3.13+, PEP 8, PEP 257
- Type hints on public classes and functions
- Dataclasses + `StrEnum` for domain types
- `pathlib` only (no `os.path`)
- No wildcard imports; avoid circular imports
- Constants in `constants.py`; CLI exit codes in `cli/commands.py`
- Logging configured only in `setup_logging()` during startup
- Deferred features raise `NotImplementedError` with an explanatory note

## Versioning strategy

1. Bump `barcode_generator/VERSION`
2. Bump `APP_VERSION` in `metadata.py` to match
3. Update `CHANGELOG.md` (Keep a Changelog)
4. `pyproject.toml` reads version dynamically from `VERSION`
5. Keep packaging name/description/license/authors aligned with `metadata.py`
6. Tag releases when publishing EXE / installer artifacts to `releases/`

## Development workflow

See `barcode_generator/README.md` for install, test, run, and build commands.
