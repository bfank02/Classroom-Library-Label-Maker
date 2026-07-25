# Barcode Generator

Python component of **Classroom Library Label Maker**.

Validates ISBN-13 values, generates EAN-13 barcode PNG images, skips existing
images, and writes a JSON results file. Packaged for Windows via PyInstaller.

**Package:** `classroom_library_label_maker`  
**Version:** see [`VERSION`](VERSION) and `metadata.APP_VERSION` · **Changes:** [`CHANGELOG.md`](CHANGELOG.md)

Product identity (name, license, authorship, CLI name) lives in
`src/classroom_library_label_maker/metadata.py` — treat that module as the
single source of truth and avoid hardcoding branding strings elsewhere.

## Requirements

- Python 3.13+
- Windows recommended for EXE packaging (`build.bat`)

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
│       ├── logger.py               # Rotating + console logging
│       ├── models.py               # Domain dataclasses / enums
│       ├── exceptions.py           # ApplicationError hierarchy
│       ├── cli/
│       │   ├── parser.py           # Argparse + subcommands
│       │   └── commands.py         # Command handlers + dispatch
│       ├── services/
│       │   ├── barcode_generation_service.py
│       │   ├── batch_processing_service.py
│       │   ├── excel_import_service.py
│       │   ├── barcode_generator.py
│       │   ├── batch_processor.py
│       │   ├── isbn_validator.py
│       │   ├── protocols.py        # Lookup / cover contracts
│       │   ├── lookups/            # Future ISBN APIs
│       │   └── covers/             # Future cover downloads
│       ├── rendering/              # Barcode image rendering (protocol + backends)
│       │   ├── renderer.py
│       │   └── barcode_renderer.py
│       ├── workbooks/              # Spreadsheet I/O (protocol + placeholder)
│       │   ├── workbook_reader.py
│       │   └── openpyxl_workbook_reader.py
│       ├── label_templates/        # Physical label specs (inches, immutable)
│       │   ├── label_template.py
│       │   ├── avery_5160.py
│       │   └── template_registry.py
│       └── utils/
│           └── file_utils.py
│
├── tests/
│   ├── conftest.py
│   ├── benchmarks/             # Manual ISBN timing (not CI)
│   ├── golden/                 # Optional golden PNGs + helpers
│   ├── assets/workbooks/       # Sample .xlsx files for import tests
│   ├── integration/                # Reserved for E2E tests
│   └── test_*.py
│
├── assets/
│   ├── icons/
│   │   ├── app.ico
│   │   └── logo.png
│   ├── templates/
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
```

Dependency split:

| Install | What you get |
|---------|----------------|
| `pip install -r requirements.txt` or `pip install .` | Runtime: `python-barcode`, `Pillow`, `openpyxl` |
| `pip install -e ".[dev]"` | + pytest, ruff, mypy, pre-commit, … |
| `pip install -e ".[build]"` | + PyInstaller |
| `pip install -e ".[dev,build]"` | Full local development (recommended) |

The PyInstaller EXE bundles only what the app imports at runtime (stdlib +
`python-barcode` + `Pillow` + `openpyxl`). Dev/build tools are never required
inside the EXE.

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

`BatchProcessingService` orchestrates Feature 1 + Feature 2 over a collection
of books: validate each ISBN, generate barcodes for valid books, continue after
per-book failures, and preserve input order in the results list.

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

- `ApplicationSettings.label_template_id` defaults to `avery-5160`
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
- `OpenPyxlLabelSheetTarget` writes centered cells (does **not** save)
- Does **not** generate barcodes, validate ISBNs, import, print, or save

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

```powershell
.\build.bat
```

Produces a one-file EXE under `dist/` (gitignored). Assets are bundled via
`--add-data`. A real `assets/icons/app.ico` is used as the EXE icon when the
file is non-empty.

## Testing

```powershell
python -m pytest
```

- Unit tests live beside fixtures in `tests/`.
- `tests/integration/` is reserved for end-to-end runs once generation works.
- `tests/golden/` holds optional reference barcode PNGs (non-brittle compares).
- Incomplete batch/label features may remain `xfail` until implemented.

### ISBN validator benchmarks (manual only)

`tests/benchmarks/` holds **engineering performance timings** for
`IsbnValidator`. They exist to spot accidental slowdowns during refactors, not
to enforce hard SLAs.

**Why they exist**

- Give developers a quick local signal when changing normalization/validation.
- Produce comparable timings across machines/commits without coupling CI to
  wall-clock variance.

**How to run**

```powershell
# Preferred: run as a script (prints timings only)
python tests\benchmarks\benchmark_isbn_validator.py

# Optional: invoke via pytest on that file alone
python -m pytest tests\benchmarks\benchmark_isbn_validator.py -v -s
```

Default `python -m pytest` does **not** collect these files (they are named
`benchmark_*.py`, not `test_*.py`).

**How to interpret results**

- Compare relative times on the **same machine** before/after a change.
- Absolute numbers vary by CPU, power plan, and background load — do not treat
  them as pass/fail gates.
- Look for order-of-magnitude regressions (e.g. 10× slower), not millisecond noise.

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

## Run (CLI)

Commands: `generate` (default), `version`, plus reserved `validate` /
`clean` / `diagnostics`.

```powershell
# Preferred explicit form
python -m classroom_library_label_maker generate `
  --input assets\sample-data\sample-books.json `
  --output-dir output\barcodes `
  --results output\results.json `
  --log-file logs\application.log

# Legacy form (still supported; maps to generate)
python -m classroom_library_label_maker `
  --input assets\sample-data\sample-books.json `
  --results output\results.json

python -m classroom_library_label_maker version
```

## Related documentation

- [Architecture](../docs/Architecture.md)
- [Public API](../docs/PublicAPI.md)
- [Developer review checklist](../docs/DeveloperReviewChecklist.md)
- [Feature review template](../docs/templates/FeatureReviewTemplate.md)
- [Barcode scan verification](../docs/Barcode%20Scan%20Verification.md)
- [Software Design Specification](../docs/Software%20Design%20Specification.md)
- [Development Roadmap](../docs/Development%20Roadmap.md)
- [Sprint tasks](../TASKS.md)
