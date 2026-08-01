# Barcode Generator

Python component of **Classroom Library Label Maker**.

Validates ISBN-13 values, imports books from Excel, generates EAN-13 barcode
PNG images, orchestrates batches, lays out labels, and **saves** a printable
label workbook. Packaged for **Windows** and **macOS** via PyInstaller from the
same shared codebase.

**Canonical pipeline:**
`WorkbookGenerationService` (also the CLI `generate` runtime) =
`ExcelImportService` → optional `BookEnrichmentService` →
`BatchProcessingService` → `LabelLayoutService` → `WorkbookWriter.save`

**Desktop GUI:** PySide6 main window collects inputs and invokes
`WorkbookGenerationService` on a background Qt worker thread (same engine as
CLI), with stage progress in the status line. Cancellation not implemented yet.
**Not implemented yet:** printing / print preview, Excel VBA UI.

**Deprecated (unused by CLI):** `BatchProcessor`, `BarcodeGenerator`,
`BatchResults` — do not use for new development.

**Package:** `classroom_library_label_maker`  
**Version:** see [`VERSION`](VERSION) and `metadata.APP_VERSION` · **Changes:** [`CHANGELOG.md`](CHANGELOG.md)

Product identity (name, license, authorship, CLI name) lives in
`src/classroom_library_label_maker/metadata.py` — treat that module as the
single source of truth and avoid hardcoding branding strings elsewhere.

## Requirements

- Python 3.13+
- PyInstaller (`pip install -e ".[build]"`) for desktop packaging
- macOS: `build_macos.sh` produces a Finder-launchable `.app`
- Windows: `build.bat` produces a windowed one-file EXE

## Folder layout

```
barcode_generator/
├── VERSION
├── CHANGELOG.md
├── pyproject.toml
├── .ruff.toml
├── .pre-commit-config.yaml
├── requirements.txt            # Runtime only (python-barcode + Pillow)
├── build.bat
├── build_macos.sh
├── scripts/
│   ├── build_release.py        # Shared PyInstaller packaging entry point
│   └── generate_app_icons.py   # logo.png / app.ico / app.icns
├── README.md
│
├── src/
│   └── classroom_library_label_maker/
│       ├── __init__.py
│       ├── __main__.py
│       ├── main.py                 # Startup only
│       ├── metadata.py             # Product identity (single source of truth)
│       ├── constants.py
│       ├── config.py               # ApplicationSettings + ProjectPaths
│       ├── runtime_paths.py        # Frozen + OS user log/data directories
│       ├── logger.py               # Rotating + console logging
│       ├── models.py               # Domain dataclasses / enums
│       ├── exceptions.py           # ApplicationError hierarchy
│       ├── cli/
│       │   ├── parser.py           # Argparse + subcommands
│       │   └── commands.py         # Command handlers + dispatch
│       ├── progress.py             # GenerationStage / GenerationProgress
│       ├── gui/                    # Desktop presentation (PySide6)
│       │   ├── __main__.py         # python -m …gui
│       │   ├── app.py              # QApplication bootstrap
│       │   ├── main_window.py      # Input form layout
│       │   ├── controller.py       # Form actions + validation
│       │   ├── generation_worker.py # Background QThread worker
│       │   └── form_state.py       # Immutable selections
│       ├── services/
│       │   ├── isbn_validator.py
│       │   ├── barcode_generation_service.py
│       │   ├── batch_processing_service.py
│       │   ├── book_enrichment_service.py  # Enrichment orchestration (null default)
│       │   ├── excel_import_service.py
│       │   ├── label_layout_service.py
│       │   ├── workbook_generation_service.py
│       │   ├── barcode_generator.py    # Deprecated CLI helper
│       │   ├── batch_processor.py      # Deprecated CLI adapter
│       │   ├── protocols.py            # Enrichment / lookup / cover / progress contracts
│       │   ├── lookups/                # GoogleBooksEnrichmentProvider (+ future)
│       │   └── covers/                 # Future cover downloads
│       ├── rendering/                  # Barcode image rendering (protocol + backends)
│       │   ├── renderer.py
│       │   └── barcode_renderer.py
│       ├── workbooks/                  # Spreadsheet read / label-sheet write
│       │   ├── workbook_reader.py
│       │   ├── openpyxl_workbook_reader.py
│       │   ├── workbook_writer.py
│       │   ├── openpyxl_workbook_writer.py
│       │   ├── workbook_presentation.py
│       │   ├── label_sheet_target.py
│       │   ├── in_memory_label_sheet_target.py
│       │   ├── in_memory_workbook_writer.py
│       │   └── openpyxl_label_sheet_target.py
│       ├── label_templates/            # Physical label specs (inches, immutable)
│       │   ├── label_template.py
│       │   ├── avery_5160.py
│       │   └── template_registry.py
│       └── utils/
│           └── file_utils.py
│
├── tests/
│   ├── conftest.py
│   ├── benchmarks/             # Manual ISBN / enrichment timings (not CI)
│   ├── golden/                 # Optional golden PNGs + helpers
│   ├── assets/workbooks/       # Sample .xlsx files for import tests
│   ├── integration/                # Reserved for E2E tests
│   └── test_*.py
│
├── assets/
│   ├── icons/
│   │   ├── app.ico
│   │   └── logo.png
│   ├── templates/              # Reserved (geometry is in label_templates/)
│   ├── sample-data/
│   │   └── sample-books.json
│   └── resources/
│
├── output/
│   └── barcodes/
├── logs/
│   └── archive/
└── temp/
```
## Development workflow

```powershell
cd barcode_generator
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -e ".[dev,build]"
python -m pytest
python -m classroom_library_label_maker --version
python -m classroom_library_label_maker.gui
```

Dependency split:

| Install | What you get |
|---------|----------------|
| `pip install -r requirements.txt` or `pip install .` | Runtime: `python-barcode`, `Pillow`, `openpyxl`, `PySide6` |
| `pip install -e ".[dev]"` | + pytest, ruff, mypy, pre-commit, … |
| `pip install -e ".[build]"` | + PyInstaller |
| `pip install -e ".[dev,build]"` | Full local development (recommended) |

The PyInstaller EXE bundles only what the app imports at runtime (stdlib +
`python-barcode` + `Pillow` + `openpyxl` + `PySide6`). Dev/build tools are
never required inside the EXE.

### Linting and formatting (Ruff)

Ruff config lives in [`.ruff.toml`](.ruff.toml) (Python 3.13, format, import
sorting, and common lint rules).

```powershell
# Check and auto-fix lint issues
python -m ruff check --fix src tests

# Apply formatter
python -m ruff format src tests
```

### Pre-commit hooks

Hooks run Ruff check (with `--fix`) and Ruff format on each commit:

```powershell
python -m pip install pre-commit
pre-commit install
pre-commit run --all-files
```

Configuration: [`.pre-commit-config.yaml`](.pre-commit-config.yaml).

Coding standards:

- Python 3.13+, PEP 8, PEP 257
- Type hints on public APIs
- Dataclasses / enums for domain types
- `pathlib.Path` for filesystem paths
- No wildcard imports; no logging configuration at import time
- Business logic in `services/`; `main.py` stays thin
- Use Ruff (via CLI or pre-commit) before opening a PR

### ISBN validation

`IsbnValidator` lives in `services/isbn_validator.py`.

**Stable public API** (backward compatible unless a major version change):

- `normalize()` — clean input without validating
- `validate()` — validate one ISBN → `ValidationResult`
- `validate_many()` — validate many ISBNs via `validate()`

```powershell
python -c "from classroom_library_label_maker.services import IsbnValidator; v=IsbnValidator(); print(v.normalize('978-0-06-440055-8'), v.validate('9780064400558').is_valid)"
```

Failure text comes from `ValidationErrorCode.message`. See
[`docs/Architecture.md`](../docs/Architecture.md) for the full contract.

### Barcode generation

`BarcodeGenerationService` creates EAN-13 PNG files for validated books:

```powershell
python -c "
from pathlib import Path
from classroom_library_label_maker.config import load_application_settings
from classroom_library_label_maker.models import Book
from classroom_library_label_maker.services import BarcodeGenerationService

settings = load_application_settings()
book = Book(isbn='9780064400558', title='Demo', author='Author', copies=1)
result = BarcodeGenerationService(settings).generate_for_book(book)
print(result.status, result.output_path)
"
```

- Output path: `{settings.barcode_output_directory}/{normalized_isbn}.png`
- Existing files return `ALREADY_EXISTS` (no overwrite)
- Rendering goes through `BarcodeRenderer` / `PythonBarcodeRenderer`
- Renderer geometry comes from `ApplicationSettings` (`barcode_module_width`,
  `barcode_module_height`, `barcode_quiet_zone`, `barcode_font_size`,
  `barcode_dpi`) — defaults match the current EAN-13 PNG look

### Batch processing

`BatchProcessingService` is the **canonical** multi-book orchestrator (Feature 1
+ Feature 2): validate each ISBN, generate barcodes for valid books, continue
after per-book failures, and preserve input order in the results list.

```powershell
python -c "from classroom_library_label_maker.config import load_application_settings; from classroom_library_label_maker.models import Book; from classroom_library_label_maker.services import BatchProcessingService; s=load_application_settings(); books=[Book(isbn='9780064400558', title='A', author='B'), Book(isbn='123', title='Bad', author='B')]; r=BatchProcessingService(s).process_books(books); print(r.to_dict()['summary'])"
```

- Returns `BatchProcessingResult` (`total_processed`, generation/skip/failure
  counts, `elapsed_seconds`, derived `books_per_second`, per-book results)
- `results` order matches the input `books` collection
- Reuses `IsbnValidator` and `BarcodeGenerationService` (no duplicated logic)
- Optional `BatchProgressReporter` for future progress UI
- Optional `BatchCancellationToken` constructor hook for future cooperative
  cancel (accepted now, **not enforced** yet)

### Book enrichment (missing ISBNs during generation)

`BookEnrichmentService` looks up missing ISBNs by title/author when
`lookup_missing_isbns` is True (default). Generation injects the default
Google Books provider via
`create_default_enrichment_service(api_key=settings.google_books_api_key)`;
the orchestrator depends only on `BookEnrichmentService`. The API key is
resolved once in `config.load_google_books_auth_config()` (never read inside
the provider).

GUI: checkbox **Look up missing ISBNs automatically** (checked by default).
Uncheck for Version 1.0 behavior (blank ISBN rows skipped at import; no
lookup stage).

**Google Books authentication**

```bash
export GOOGLE_BOOKS_API_KEY="your-restricted-books-api-key"
```

* Missing / unset → anonymous mode (slower pacing, still supported)
* Empty / whitespace → disabled (invalid configuration); anonymous requests
* Non-empty → authenticated mode (~0.40s pacing); appends `key=` on requests
* Startup logs authentication state once (never logs the key)
* Rejected keys (401/403) fall back to anonymous for the rest of the run

**Packaged desktop apps** launched from Finder/Dock do **not** inherit shell
exports. Install the key once with:

```powershell
python scripts\install_google_books_api_key.py
```

(or write a one-line `google_books_api_key.txt` under the per-user Application
Support / LOCALAPPDATA app folder). Prefer the env var in development; prefer
the key file for packaged builds.

Progress stage: **"Looking up missing ISBNs..."**, then **"(n of total)"** as
each book is looked up. Large inventories (e.g. the teacher demo) are much
faster with a key, but still paced and will back off on HTTP 429. Results are
summarized in
`EnrichmentSummary` on `WorkbookGenerationResult` (consumed by GUI/CLI/logs).
When some books still need attention, the completion message includes an
**ISBN Lookup Summary** with found/needs-review counts and up to five titles.

- In-memory cache on the service (normalized title+author; all statuses except
  transient rate-limit errors)
- Ambiguous / not-found / errors become warnings; generation continues
- Teacher inventory workbook is never modified
- Matching strategy: [`docs/Architecture.md`](../docs/Architecture.md)
- Public surface: [`docs/PublicAPI.md`](../docs/PublicAPI.md)

**Google Books search flow (developer notes)**

Queries run most-specific-first (`intitle:… inauthor:surname` →
`title inauthor:surname` → free-text `title author`). A confident catalog
match **without** a usable ISBN does not stop the search; later strategies
still run. Confidence thresholds and ambiguity detection are unchanged.
Enable DEBUG logging on the `google_books` logger to see per-query
diagnostics (query text, result counts, top candidates, continuation, final
decision). Diagnostics never include API keys.

### Excel import

`ExcelImportService` maps workbook rows to `Book` objects via `WorkbookReader`:

```powershell
python -c "from classroom_library_label_maker.config import load_application_settings; from classroom_library_label_maker.services import ExcelImportService; s=load_application_settings(workbook_path=r'tests\assets\workbooks\valid_books.xlsx'); r=ExcelImportService(s).import_books(); print(r.imported_rows, r.books[0].title)"
```

- Column/sheet settings live on `ApplicationSettings` (not hardcoded)
- Blank rows are skipped; malformed rows become `ImportWarning` entries
- Returns `ImportResult` (`books`, `source_rows`, counts, warnings, timing)
- `ImportResult` / `ImportWarning` are immutable value objects
- Does **not** validate ISBNs or generate barcodes
- Workbook template versioning is an extension point only (not enforced yet);
  see Architecture.md for where version metadata and checks will live

### Label templates

Immutable physical sheet specs (inches) live under `label_templates/`:

```powershell
python -c "from classroom_library_label_maker.label_templates import create_default_template_registry; t=create_default_template_registry().get('avery-5160'); print(t.template_name, t.labels_per_page, t.label_width)"
```

- `ApplicationSettings.label_template_id` is the **single source of truth**
  (default `avery-5160`); `default_label_type` is deprecated and unused by layout
- `TemplateRegistry` looks up templates; unknown ids raise `ConfigurationError`
- `LabelLayoutService` consumes `LabelTemplate` without knowing vendors
- Add new templates by registering `LabelTemplateSpec` instances (no layout-engine changes)

### Label layout

`LabelLayoutService` arranges books onto worksheet pages using the selected
`LabelTemplate` and a `LabelSheetTarget` (no direct openpyxl dependency):

```powershell
python -c "from classroom_library_label_maker.config import load_application_settings; from classroom_library_label_maker.models import Book; from classroom_library_label_maker.services import LabelLayoutService; from classroom_library_label_maker.workbooks import InMemoryLabelSheetTarget; s=load_application_settings(); books=[Book(isbn='9780064400558', title='A', author='B')]; r=LabelLayoutService(s).layout_books(books, InMemoryLabelSheetTarget()); print(r.to_dict()['summary'])"
```

- Paginates when a page is full; never silently discards labels
- Returns `LabelLayoutResult` (`pages_created`, `labels_placed`,
  `empty_labels_remaining_on_last_page`, `elapsed_seconds`, warnings)
- Optional `barcode_paths` map ISBN → PNG; missing images use placeholders
- `OpenPyxlLabelSheetTarget` writes centered cells; `OpenPyxlWorkbookWriter`
  persists the workbook
- Does **not** generate barcodes, validate ISBNs, import, or print
- **Printing is not implemented** (workbook save is)

### Workbook generation (end-to-end)

`WorkbookGenerationService` runs the full pipeline and saves a label workbook:

```powershell
python -c "from pathlib import Path; from classroom_library_label_maker.config import load_application_settings; from classroom_library_label_maker.services import WorkbookGenerationService; s=load_application_settings(workbook_path=r'tests\assets\workbooks\valid_books.xlsx'); r=WorkbookGenerationService(s).generate(output_path=Path('temp')/'library_labels.xlsx'); print(r.to_dict()['summary'])"
```

- Returns `WorkbookGenerationResult` (import/batch/layout/save statistics)
- Default output: `{project_root}/output/library_labels.xlsx`
- Depends on `WorkbookWriter` only for Excel output (never imports openpyxl)
- Does **not** print or show UI
- The CLI `generate` command is a thin adapter over this service

### Workbook presentation (print readiness)

Separate from generation orchestration. Applied by openpyxl adapters when
pages are created / the workbook is saved:

- Document properties (title, subject, author)
- Active sheet = first `Labels N` worksheet
- Hidden gridlines, 100% zoom
- Page orientation, paper size, and margins from `LabelTemplate`
- Print area covering the label grid; fit-to-width; horizontal print centering
- Consistent label fonts; long titles wrap in-cell

Teachers can open the `.xlsx` and use Excel **Print** without manual setup.
This project still does **not** send jobs to a printer.

## Desktop GUI

Presentation-only PySide6 desktop app. Official launch methods (after editable
install):

```powershell
# Canonical (development / from source)
python -m classroom_library_label_maker.gui

# Installed console script (same entry point)
label-maker-gui
```

Both call `classroom_library_label_maker.gui:main`, which creates
`QApplication`, shows `MainWindow`, and runs the Qt event loop.

### Current user workflow

The main window collects generation inputs and runs the engine **in the
background**:

1. **Inventory workbook** — Browse… (Excel `.xlsx` / `.xlsm`; dialog opens in
   the sample folder when `Sample Books.xlsx` is present)
2. **Barcode folder** — Browse… (starts in Documents)
3. **Label workbook** — Browse… (save dialog defaults to
   `Documents/library_labels.xlsx`; extension preserved / applied
   automatically)
4. **Label template** — combo (default **Avery 5160**)
5. **Generate Labels** — enabled when all fields validate; starts
   `WorkbookGenerationService` on a Qt worker thread

Teacher quick start: [`docs/Quick Start.md`](../docs/Quick%20Start.md).
Sample inventory: `assets/sample-data/Sample Books.xlsx` (also
`samples/Sample Books.xlsx` at the repo root).

While generating, Browse buttons, the template combo, and Generate are
disabled. The status line shows engine stage updates, then a clean success,
success-with-warnings (review before printing), or friendly error message.
Press **Esc** to close the window.

Icon loading prefers the platform-native icon (`app.icns` on macOS, `app.ico`
on Windows), then `logo.png`.

### Package layout

| Module | Role |
|--------|------|
| `gui/app.py` | `QApplication` bootstrap + event loop + icon |
| `gui/icons.py` | Application icon discovery (empty placeholders ignored) |
| `gui/main_window.py` | Widgets / layout / accessibility / Esc to close |
| `gui/controller.py` | Form actions, validation, start/finish generation |
| `gui/generation_worker.py` | `QObject` worker: run service, emit progress/completed/failed |
| `gui/form_state.py` | Immutable selections + validation messages |
| `progress.py` | Qt-free `GenerationStage` / `GenerationProgress` / reporter protocol |

- Importing `classroom_library_label_maker.gui` does not start Qt; only `main()`
  does
- Controller must not contain ISBN / import / barcode / layout business logic
- Worker must not touch widgets; service must not import Qt
- Progress originates in `WorkbookGenerationService` (reusable by a future CLI)
- Native `QFileDialog` for files and folders (no platform-specific branches)
- GUI and CLI share `WorkbookGenerationService` (identical generation path)

## CLI

Commands: `generate` (default), `version`, plus reserved `validate` /
`clean` / `diagnostics`.

```powershell
# Preferred explicit form
python -m classroom_library_label_maker generate `
  --input tests\assets\workbooks\valid_books.xlsx `
  --output-dir output\barcodes `
  --labels-output output\library_labels.xlsx `
  --results output\results.json `
  --log-file logs\application.log

# Flat flags still map to generate (no subcommand)
python -m classroom_library_label_maker `
  --input tests\assets\workbooks\valid_books.xlsx `
  --labels-output output\library_labels.xlsx

python -m classroom_library_label_maker version
```

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Invalid arguments |
| 2 | Input / import failure |
| 3 | Generation failure |
| 4 | Unexpected internal error |
| 5 | Reserved command not implemented |

On success, `generate` prints a concise summary from `WorkbookGenerationResult`
(books imported/processed, labels, pages, barcodes generated/reused, output
path, elapsed time).

### Manual barcode verification

After changing renderer settings or dependencies, scan a sample PNG and confirm
the decode equals the normalized ISBN-13 (example: **`9780064400558`**).

Full checklist: [`docs/Barcode Scan Verification.md`](../docs/Barcode%20Scan%20Verification.md).

### Golden barcode images

`tests/golden/` stores optional known-good reference PNGs and comparison
helpers. Comparisons use size tolerance + average-hash distance — **not**
pixel-perfect or byte-identical checks. Missing goldens skip. See
[`tests/golden/README.md`](tests/golden/README.md) for update steps
(`UPDATE_GOLDEN=1`).

## Build process

Shared packaging lives in `scripts/build_release.py`. Platform wrappers:

```bash
# macOS — native .app bundle (no Python required at runtime)
./build_macos.sh
open "dist/Classroom Library Label Maker.app"
```

```powershell
# Windows — windowed one-file EXE
.\build.bat
```

Both builds:

- package the **GUI** entry point (not the CLI)
- bundle `assets/` (templates, sample workbook, icons, staged Quick Start)
- bundle `VERSION`
- embed product metadata from `metadata.py`

The Quick Start guide is staged at build time from `docs/Quick Start.md` into
`assets/resources/` (not duplicated as a second source file in git).

## Testing

```powershell
python -m pytest
```

- Unit tests live beside fixtures in `tests/`.
- `tests/integration/` holds the production-readiness end-to-end test (real
  openpyxl writer + canonical inventory workbook). See
  [`tests/integration/README.md`](tests/integration/README.md).
- `tests/golden/` holds optional reference barcode PNGs (non-brittle compares).
- Remaining `xfail`s are primarily the deprecated CLI JSON `load_books` /
  `BarcodeGenerator.generate` stubs — not the Feature 1–7 library services.

```powershell
# Integration only (real adapters, temp dirs only)
python -m pytest tests\integration -v
```

### Performance benchmarks (manual only)

`tests/benchmarks/` holds **engineering performance timings**. They exist to
spot accidental slowdowns during refactors, not to enforce hard SLAs. They are
**not** CI gates.

**ISBN validator**

```powershell
python tests\benchmarks\benchmark_isbn_validator.py
# optional:
python -m pytest tests\benchmarks\benchmark_isbn_validator.py -v -s
```

**Google Books enrichment** (Teacher Demo Library; network required; optional
`GOOGLE_BOOKS_API_KEY`). Reports total books, missing ISBNs, requests, cache
hits/misses, 429 retries, and wall time — never prints API keys:

```powershell
python tests\benchmarks\benchmark_google_books_enrichment.py
```

Default `python -m pytest` does **not** collect these files (they are named
`benchmark_*.py`, not `test_*.py`).

**How to interpret results**

- Compare relative times on the **same machine** before/after a change.
- Absolute numbers vary by CPU, power plan, network, and quota — do not treat
  them as pass/fail gates.
- Look for order-of-magnitude regressions, not millisecond noise.

**CI policy**

- Benchmarks must **never** fail CI.
- Do not add performance assertions or include `tests/benchmarks/` in required
  CI test paths.

## Versioning

- Python source of truth for identity: `metadata.py`
- On-disk SemVer file: [`VERSION`](VERSION) (also used by setuptools)
- Keep `APP_VERSION` and `VERSION` identical when releasing
- Human history: Keep a Changelog in [`CHANGELOG.md`](CHANGELOG.md)
- Semantic Versioning: `MAJOR.MINOR.PATCH`

## Related documentation

- [Architecture](../docs/Architecture.md)
- [Public API](../docs/PublicAPI.md)
- [Developer review checklist](../docs/DeveloperReviewChecklist.md)
- [Feature review template](../docs/templates/FeatureReviewTemplate.md)
- [Barcode scan verification](../docs/Barcode%20Scan%20Verification.md)
- [Software Design Specification](../docs/Software%20Design%20Specification.md)
- [Development Roadmap](../docs/Development%20Roadmap.md)
- [Sprint tasks](../TASKS.md)
