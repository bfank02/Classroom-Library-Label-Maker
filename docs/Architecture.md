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
     Services       BatchProcessor → IsbnValidator / BarcodeGenerator
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
│   ├── barcode_generator.py
│   ├── batch_processor.py
│   ├── protocols.py
│   ├── lookups/         Future catalog APIs
│   └── covers/          Future cover downloads
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
| `utils.file_utils` | JSON + directory helpers |
| `constants` | Operational defaults (paths, log sizes) — not product branding |

## ISBN validator (`services/isbn_validator.py`)

`IsbnValidator` (alias `ISBNValidator`) is a **stateless** normalizer/validator.
It never raises for expected ISBN failures; it always returns
`ValidationResult`.

| Method | Role |
|--------|------|
| `normalize(isbn)` | Public cleaner: trim + remove spaces/hyphens; **no** validation |
| `validate(isbn)` | Full ISBN-13 checks in fixed order; returns `ValidationResult` |
| `validate_many(isbns)` | Applies `validate()` to each item (no duplicated rules) |
| `is_valid(isbn)` | Boolean wrapper around `validate()` |
| `compute_check_digit(12 digits)` | GS1 / ISBN-13 check-digit helper |

Validation order: empty → numeric → length 13 → prefix `978`/`979` → checksum.

`ValidationErrorCode` is the single source of truth for failure **codes and
default user-facing messages** (`error_code.message`). `ValidationResult.errors`
is populated from that message.

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
books JSON
    │
    ▼
ApplicationSettings ──► BatchProcessor.run()
    │                          │
    │                          ▼
    │                   load_books() ──► list[Book]
    │                          │
    │                          ▼
    │                   process_book() per item
    │                     ├─ IsbnValidator.validate()
    │                     ├─ optional lookup / cover hooks
    │                     └─ BarcodeGenerator.generate_if_missing()
    │                          │
    │                          ▼
    │                   list[BarcodeGenerationResult]
    │                          │
    └──────────► results JSON + output/barcodes/*.png
                 logs/application.log (rotating)
```

## Folder purposes

| Path | Tracked? | Purpose |
|------|----------|---------|
| `src/classroom_library_label_maker/` | Yes | Installable Python package |
| `tests/` | Yes | Unit tests; `integration/` reserved |
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
4. **Inventory / checkout / reading levels** — extend `Book` optional fields
5. **Multiple label templates** — `assets/templates/` + `default_label_type`
6. **Additional barcode formats** — new generator strategies beside EAN-13
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
