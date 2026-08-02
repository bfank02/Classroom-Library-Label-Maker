# Classroom Library Label Maker

Create barcode labels for your classroom library.

## For teachers

Start here: [`docs/Quick Start.md`](docs/Quick%20Start.md)

1. Prepare an **inventory workbook** (Excel sheet named `Books` with columns
   `ISBN`, `Title`, `Author`, `Copies`) — or open `samples/Sample Books.xlsx`
   (small starter) / `samples/Teacher Demo Library.xlsx` (large manual-QA demo).
2. Run the app. The Home screen has an application header plus **Files**,
   **Options**, and **Actions** sections. In **Files**, choose your inventory
   workbook, a barcode folder, a label folder, and the label file name (paths
   and the filename are remembered after the first selection). In **Options**,
   optionally leave **Look up missing ISBNs automatically** checked so blank
   ISBN cells are filled from title/author.
3. In **Actions**, click **Generate Labels** (status messages appear in that
   section). If some books still need ISBN choices, a
   **Review ISBN Matches** wizard lets you pick a catalog match, enter an ISBN
   manually, or skip (clear Progress / book / match sections; Skip and
   selections advance automatically; Finish Review appears on the last book).
   Optionally leave **Save updated inventory workbook** checked to create
   `Inventory (Updated ISBNs).xlsx` beside your original (the original file
   is never overwritten). When generation finishes, a **✔ Ready to Print**
   page lists what was created and lets you open the files or click **Done**
   to return Home. Then print the label workbook on Avery 5160 sheets.

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
├── samples/                      # Example inventory workbooks (manual QA / demos)
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

## Manual testing sample

For end-to-end demos (ISBN lookup, review wizard, multi-page labels, inventory
update), use
[`samples/Teacher Demo Library.xlsx`](samples/Teacher%20Demo%20Library.xlsx)
(~190 classroom titles with mixed valid / blank / invalid ISBNs). Keep
`samples/Sample Books.xlsx` for a small smoke-test list. Do not use the demo
workbook as an automated integration-test asset.

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
