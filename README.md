# Classroom Library Label Maker

Create barcode labels for your classroom library.

## Layout

```
ClassroomLibraryLabelMaker/
├── docs/                         # Architecture, design, roadmap
├── excel/                        # Excel workbook + VBA
├── barcode_generator/            # Python barcode engine (src-layout package)
│   ├── src/classroom_library_label_maker/
│   ├── tests/
│   ├── assets/                   # Icons, samples, templates, resources
│   ├── output/barcodes/          # Runtime PNGs (not committed)
│   ├── logs/                     # Runtime logs + archive/ (not committed)
│   └── temp/                     # Scratch files (not committed)
├── installer/                    # Packaging / setup
├── samples/                      # Example workbooks
├── releases/                     # Distribution artifacts
├── TASKS.md
├── LICENSE
└── README.md
```

## Getting started

1. Read [`docs/Architecture.md`](docs/Architecture.md) for system structure and data flow.
2. Follow [`barcode_generator/README.md`](barcode_generator/README.md) for Python setup, tests, and builds.
3. Track delivery in [`TASKS.md`](TASKS.md).

Design notes:

- [`docs/Software Design Specification.md`](docs/Software%20Design%20Specification.md)
- [`docs/Development Roadmap.md`](docs/Development%20Roadmap.md)

## Development workflow (summary)

```powershell
cd barcode_generator
python -m pip install -e ".[dev,build]"
python -m pytest
python -m classroom_library_label_maker --version
```

Runtime folders (`output/`, `logs/`, `temp/`) hold generated files and are
ignored by Git except for `.gitkeep` placeholders.
