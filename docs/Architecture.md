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

## Package layout (src-layout)

```
barcode_generator/src/classroom_library_label_maker/
├── main.py              CLI / process entry only
├── config.py            ApplicationSettings, ProjectPaths, VERSION
├── logger.py            Console + RotatingFileHandler (setup only at runtime)
├── models.py            Book, ValidationResult, BarcodeGenerationResult, …
├── constants.py         Shared names / defaults (no magic strings in services)
├── services/            Business orchestration
│   ├── isbn_validator.py
│   ├── barcode_generator.py
│   ├── batch_processor.py
│   ├── protocols.py     IsbnLookupService / CoverDownloadService
│   ├── lookups/         Future catalog APIs
│   └── covers/          Future cover downloads
└── utils/               Generic I/O helpers
```

Import style (absolute, package-qualified):

```python
from classroom_library_label_maker.services import BatchProcessor
from classroom_library_label_maker.config import load_application_settings
```

## Package responsibilities

| Area | Responsibility |
|------|----------------|
| `main` | Parse CLI, load settings, configure logging, run batch |
| `models` | Domain dataclasses and `BarcodeStatus` enum |
| `config` | Discover project root, VERSION, asset/runtime paths |
| `logger` | Production logging setup (no import-time side effects) |
| `services.*` | Validation, generation, batch orchestration |
| `services.protocols` | Extension contracts for lookups / covers |
| `utils.file_utils` | JSON + directory helpers |

## Data flow

```
sample-books.json / caller JSON
            │
            ▼
   ApplicationSettings ──► BatchProcessor.run()
            │                      │
            │                      ▼
            │               load_books() ──► list[Book]
            │                      │
            │                      ▼
            │               process_book() per item
            │                 ├─ IsbnValidator.validate()
            │                 ├─ optional lookup / cover hooks
            │                 └─ BarcodeGenerator.generate_if_missing()
            │                      │
            │                      ▼
            │               list[BarcodeGenerationResult]
            │                      │
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

Designed for growth without rewriting the batch pipeline:

1. **ISBN lookup APIs** — implement `IsbnLookupService` under `services/lookups/`
2. **Cover downloads** — implement `CoverDownloadService` under `services/covers/`
3. **Inventory / checkout / reading levels** — extend `Book` optional fields and
   Excel sheets; keep JSON contracts versioned
4. **Multiple label templates** — files in `assets/templates/` selected via
   `ApplicationSettings.default_label_type`
5. **Additional barcode formats** — new generator strategies beside EAN-13
6. **Auto-update / installer** — `installer/` + `releases/`; VERSION drives
   update checks later

```
ExtensibilityHooks ──► BatchProcessor
        │
        ├─ IsbnLookupService (protocols)
        └─ CoverDownloadService (protocols)
```

## Coding standards

- Python 3.13+, PEP 8, PEP 257
- Type hints on public classes and functions
- Dataclasses + `StrEnum` for domain types
- `pathlib` only (no `os.path`)
- No wildcard imports; avoid circular imports
- Constants live in `constants.py`
- Logging configured only in `setup_logging()` during startup
- Deferred feature work raises `NotImplementedError` with an explanatory note
  (no silent stubs)

## Versioning strategy

1. Bump `barcode_generator/VERSION`
2. Update `CHANGELOG.md` (Keep a Changelog)
3. Align `pyproject.toml` project version
4. Tag releases when publishing EXE / installer artifacts to `releases/`

## Development workflow

See `barcode_generator/README.md` for install, test, run, and build commands.
