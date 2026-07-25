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
├── requirements.txt
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
│       │   ├── barcode_generator.py
│       │   ├── batch_processor.py
│       │   ├── isbn_validator.py
│       │   ├── protocols.py        # Lookup / cover contracts
│       │   ├── lookups/            # Future ISBN APIs
│       │   └── covers/             # Future cover downloads
│       ├── rendering/              # Barcode image rendering (protocol + backends)
│       │   ├── renderer.py
│       │   └── barcode_renderer.py
│       └── utils/
│           └── file_utils.py
│
├── tests/
│   ├── conftest.py
│   ├── benchmarks/             # Manual ISBN timing (not CI)
│   ├── golden/                 # Optional golden PNGs + helpers
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
- [Barcode scan verification](../docs/Barcode%20Scan%20Verification.md)
- [Software Design Specification](../docs/Software%20Design%20Specification.md)
- [Development Roadmap](../docs/Development%20Roadmap.md)
- [Sprint tasks](../TASKS.md)
