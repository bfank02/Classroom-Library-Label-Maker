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
│  └─────────────┘   status / paths    └──────────┬───────────┘ │
│                                                 │             │
│                                                 ▼             │
│                                      output/barcodes/*.png    │
│                                      results JSON             │
│                                                 │             │
│  ┌─────────────┐   Avery templates   ┌──────────▼───────────┐ │
│  │ Label print │ ◄────────────────── │ assets/templates/    │ │
│  │ (Sprint 3)  │                     └──────────────────────┘ │
│  └─────────────┘                                              │
│                                                               │
│  installer/ → ships EXE + workbook     releases/ → artifacts  │
└───────────────────────────────────────────────────────────────┘
```

## Startup sequence / application lifecycle

```
Workbook / caller
        │
        │  (JSON path, or future VBA → EXE)
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
     Services       BatchProcessingService → IsbnValidator / BarcodeGenerationService
        │
        ▼
      Output        output/barcodes/*.png  +  results JSON  +  logs/
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
└── FileSystemError
```

- Defined in `exceptions.py`
- Support an optional underlying `cause` (set as `__cause__`) for logging
- CLI catches `ApplicationError` for clean user-facing failures
- Feature code should raise these instead of bare `Exception` once implemented

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
├── services/
│   ├── isbn_validator.py
│   ├── barcode_generation_service.py
│   ├── batch_processing_service.py
│   ├── barcode_generator.py
│   ├── batch_processor.py
│   ├── protocols.py
│   ├── lookups/         Future catalog APIs
│   └── covers/          Future cover downloads
├── rendering/           Barcode image rendering (library-agnostic)
│   ├── renderer.py      BarcodeRenderer protocol
│   └── barcode_renderer.py  PythonBarcodeRenderer (EAN-13 PNG)
└── utils/
    └── file_utils.py
```

Import style (absolute, package-qualified):

```python
from classroom_library_label_maker.services import BatchProcessor
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
| `metadata` | Single source of truth for product identity |
| `models` | Domain dataclasses and `BarcodeStatus` enum |
| `exceptions` | Typed application errors |
| `config` | Project root, VERSION, asset/runtime paths |
| `logger` | Production logging setup (no import-time side effects) |
| `services.*` | Validation, generation, batch orchestration |
| `services.protocols` | Extension contracts for lookups / covers |
| `rendering` | Library-agnostic barcode image rendering |
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
**not** part of the normal unit-test suite and must **never** fail CI. See the
barcode generator README for how to run them and how to interpret results.

## Rendering layer (`rendering/`)

Barcode **image encoding** is isolated from business logic so the generation
service can orchestrate skip rules and results without depending on a specific
barcode library.

```
Application (CLI / future Excel)
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

`BatchProcessingService` is the orchestration layer for collections of `Book`
objects. Future Excel import will feed books into this service.

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

JSON loading / `BatchProcessor.run()` remain separate (workbook/CLI input
adapters).

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

## Data flow (generate command)

```
books JSON / future Excel adapter
    │
    ▼
list[Book]
    │
    ▼
BatchProcessingService.process_books()
    │
    ├─ IsbnValidator.validate()
    └─ BarcodeGenerationService.generate_for_book()  (valid only)
    │
    ▼
BatchProcessingResult  (counts, elapsed_seconds, per-book outcomes)
    │
    ▼
results JSON + output/barcodes/*.png   (CLI / BatchProcessor adapters)
logs/application.log (rotating)
```

`BatchProcessor.run()` remains the CLI adapter that will load JSON and write
results once `load_books` is implemented; core orchestration is
`BatchProcessingService`.

## Folder purposes

| Path | Tracked? | Purpose |
|------|----------|---------|
| `src/classroom_library_label_maker/` | Yes | Installable Python package |
| `tests/` | Yes | Unit tests; `integration/` reserved |
| `tests/golden/` | Yes | Optional golden barcode PNGs + helpers |
| `assets/icons/` | Yes | EXE icon + logo placeholders |
| `assets/templates/` | Yes | Future Avery / label templates |
| `assets/sample-data/` | Yes | Example JSON payloads |
| `assets/resources/` | Yes | Misc static resources |
| `output/barcodes/` | Structure only | Generated PNGs |
| `logs/` + `logs/archive/` | Structure only | App log + rotated backups |
| `temp/` | Structure only | Scratch workspace |
| `VERSION` | Yes | SemVer for this component |

## Future extension points

1. **CLI commands** — `validate`, `clean`, `diagnostics` already registered
2. **ISBN lookup APIs** — `IsbnLookupService` under `services/lookups/`
3. **Cover downloads** — `CoverDownloadService` under `services/covers/`
4. **Rendering backends** — additional `BarcodeRenderer` implementations under
   `rendering/` (SVG, QR, Code128, alternate libraries)
5. **Inventory / checkout / reading levels** — extend `Book` optional fields
6. **Multiple label templates** — `assets/templates/` + `default_label_type`
7. **Auto-update / installer** — `installer/` + `releases/` driven by `VERSION`

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
