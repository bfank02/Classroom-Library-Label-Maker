# Classroom Library Label Maker

Create barcode labels for your classroom library.

## For teachers

Start here: [`docs/Quick Start.md`](docs/Quick%20Start.md)

**Windows (recommended):** download
`Classroom-Library-Label-Maker-1.0.2-windows.zip` from GitHub Releases, unzip,
and run `Classroom Library Label Maker.exe`.

1. Prepare an **inventory workbook** (Excel sheet named `Books` with columns
   `ISBN`, `Title`, `Author`, `Copies`) — or open the included
   `Sample Books.xlsx`.
2. Choose your inventory workbook, a barcode folder, and where to save the
   **label workbook**.
3. Click **Generate Labels**, then open the label workbook in Excel and print
   on Avery 5160 sheets.

Release packaging details: [`docs/Release.md`](docs/Release.md).

## Layout

```
ClassroomLibraryLabelMaker/
├── docs/                         # Architecture, design, roadmap, Quick Start
├── excel/                        # Excel workbook + VBA (future)
├── barcode_generator/            # Python barcode engine (src-layout package)
│   ├── src/classroom_library_label_maker/
│   ├── tests/
│   ├── assets/                   # Icons, samples, templates, resources
│   ├── output/barcodes/          # Runtime PNGs (not committed)
│   ├── logs/                     # Runtime logs + archive/ (not committed)
│   └── temp/                     # Scratch files (not committed)
├── installer/                    # Packaging / setup
├── samples/                      # Example inventory workbook
├── releases/                     # Distribution artifacts
├── TASKS.md
├── LICENSE
└── README.md
```

## For developers

1. Read [`docs/Architecture.md`](docs/Architecture.md) for system structure and data flow.
2. Follow [`barcode_generator/README.md`](barcode_generator/README.md) for Python setup, tests, and builds.
3. Track delivery in [`TASKS.md`](TASKS.md).

Design notes:

- [`docs/Quick Start.md`](docs/Quick%20Start.md) — teacher-facing one-pager
- [`docs/Architecture.md`](docs/Architecture.md)
- [`docs/PublicAPI.md`](docs/PublicAPI.md)
- [`docs/DeveloperReviewChecklist.md`](docs/DeveloperReviewChecklist.md)
- [`docs/templates/FeatureReviewTemplate.md`](docs/templates/FeatureReviewTemplate.md)
- [`docs/Software Design Specification.md`](docs/Software%20Design%20Specification.md)
- [`docs/Development Roadmap.md`](docs/Development%20Roadmap.md)

## Development workflow (summary)

```powershell
cd barcode_generator
python -m pip install -e ".[dev,build]"
python -m pytest
python -m classroom_library_label_maker --version
python -m classroom_library_label_maker.gui
```

Runtime folders (`output/`, `logs/`, `temp/`) hold generated files and are
ignored by Git except for `.gitkeep` placeholders.
