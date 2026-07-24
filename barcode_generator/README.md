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
│       │   ├── barcode_generator.py
│       │   ├── batch_processor.py
│       │   ├── isbn_validator.py
│       │   ├── protocols.py        # Lookup / cover contracts
│       │   ├── lookups/            # Future ISBN APIs
│       │   └── covers/             # Future cover downloads
│       └── utils/
│           └── file_utils.py
│
├── tests/
│   ├── conftest.py
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

Coding standards:

- Python 3.13+, PEP 8, PEP 257
- Type hints on public APIs
- Dataclasses / enums for domain types
- `pathlib.Path` for filesystem paths
- No wildcard imports; no logging configuration at import time
- Business logic in `services/`; `main.py` stays thin

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
- Incomplete engine features remain `xfail` until implemented.

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

> Core ISBN check-digit validation and PNG generation still raise
> `NotImplementedError` by design until Sprint 1 feature work.
## Related documentation

- [Architecture](../docs/Architecture.md)
- [Software Design Specification](../docs/Software%20Design%20Specification.md)
- [Development Roadmap](../docs/Development%20Roadmap.md)
- [Sprint tasks](../TASKS.md)
