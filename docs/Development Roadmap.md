# Development Roadmap

## Coding standards (ongoing)

- Python 3.13+, PEP 8 / PEP 257, type hints, dataclasses, `pathlib`
- Package: `classroom_library_label_maker` under `barcode_generator/src/`
- Thin `main.py`; business logic in `services/`
- Logging configured only at startup (`RotatingFileHandler` + console)
- VERSION + CHANGELOG for releases

## Phase 1 — Foundation / Barcode Engine

- [x] Project scaffolding and documentation
- [x] Proper src-layout Python package
- [x] Domain models (`Book`, `ValidationResult`, `BarcodeGenerationResult`, …)
- [x] Configuration (`ApplicationSettings`, `ProjectPaths`, VERSION)
- [x] Production logging skeleton
- [x] Test framework + fixtures / integration placeholder
- [x] ISBN-13 check-digit validation
- [x] Rendering package scaffold (`BarcodeRenderer` / `PythonBarcodeRenderer`)
- [x] EAN-13 PNG generation (`BarcodeGenerationService` + python-barcode / Pillow)
- [ ] JSON book loading (`BatchProcessor.load_books`)
- [ ] Package as EXE (`build.bat` / PyInstaller)

## Phase 2 — Excel Integration

- [ ] Excel workbook skeleton and VBA module layout
- [ ] Dashboard sheet
- [ ] Books sheet (aligned with `Book` fields)
- [ ] Generate Barcodes button → invoke EXE / JSON contract
- [ ] Status updates from results JSON

## Phase 3 — Label Printing

- [ ] Avery 5160 layout under `assets/templates/`
- [ ] Label generation from barcodes + book metadata
- [ ] Print preview

## Phase 4 — Packaging & distribution

- [ ] Installer / setup under `installer/`
- [ ] Sample books workbook under `samples/`
- [ ] First public release under `releases/`

## Phase 5 — Extensibility

- [ ] ISBN lookup providers (`services/lookups/`)
- [ ] Cover image downloads (`services/covers/`)
- [ ] Inventory / checkout / reading-level workflows
- [ ] Additional barcode symbologies and label types
- [ ] Automatic updates

See also: [`Architecture.md`](Architecture.md), [`../TASKS.md`](../TASKS.md).
