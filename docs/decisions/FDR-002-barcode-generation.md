# Feature Decision Record 002

## Barcode Generation Engine

### Status

Accepted

### Date

2026-07-24

### Purpose

Provide a reusable engine that turns a validated book ISBN into a scannable
EAN-13 barcode PNG. Downstream components (batch processing, Excel, labels)
should call this service rather than embedding barcode libraries themselves.

### Scope

This feature is responsible for:

- Accepting a validated `Book` and generating an EAN-13 PNG
- Resolving output paths from `ApplicationSettings`
- Creating output directories when missing
- Skipping generation when the target file already exists
- Delegating image encoding to a `BarcodeRenderer` implementation
- Returning a structured `BarcodeGenerationResult`
- Logging start, success, skip, render, and filesystem failures
- Mapping unexpected failures to the application exception hierarchy

### Out of Scope

- ISBN validation (owned by Feature 1)
- Excel / workbook integration
- Batch orchestration over many books
- Label layout and printing
- User interface
- Overwrite / regenerate of existing PNGs
- Alternate symbologies or vector formats

### Design Decisions

**Separation of validation from generation.**  
`BarcodeGenerationService` assumes the ISBN is already valid. It may normalize
formatting for filenames but does not re-run check-digit validation. That keeps
the generation engine focused and avoids duplicating Feature 1 policy.

**`BarcodeRenderer` abstraction.**  
Encoding is isolated behind a protocol so services never import python-barcode
or Pillow. `PythonBarcodeRenderer` is the current backend; alternate backends
can be swapped without changing callers.

**`ApplicationSettings` for paths and render geometry.**  
Output directory and renderer options (module width/height, quiet zone, font
size, DPI) come from settings/constants, not hardcoded call sites. Defaults
preserve the established EAN-13 PNG appearance.

**Structured `BarcodeGenerationResult`.**  
Callers receive status (`GENERATED`, `ALREADY_EXISTS`, etc.), ISBN, path, and
message instead of relying on side effects or exceptions for expected outcomes.

**Skip existing files.**  
If `{normalized_isbn}.png` already exists, return `ALREADY_EXISTS` and do not
overwrite. Safe for re-runs and shared classroom workflows.

**No direct Excel dependency.**  
Generation is a pure Python service over domain models. Excel import is a
separate adapter (`ExcelImportService` / `WorkbookReader`) and must not be
wired into this service.

### Public API

Primary surface:

| Symbol | Role |
|--------|------|
| `BarcodeGenerationService` | Orchestrates generation for one book |
| `BarcodeGenerationService.generate_for_book(book)` | Create or skip PNG; return result |
| `BarcodeGenerationService.output_path_for(isbn)` | Resolve configured output path |
| `BarcodeRenderer` | Protocol: `render_to_file(data, output_path, *, symbology)` |
| `PythonBarcodeRenderer` | Default EAN-13 PNG backend |
| `BarcodeSymbology` | Symbology identifiers (`EAN13` implemented) |
| `BarcodeGenerationResult` / `BarcodeStatus` | Structured outcome models |

Typical usage: construct `BarcodeGenerationService(settings)` (optionally with a
custom renderer) and call `generate_for_book(book)`.

### Testing & Validation

- Unit tests cover success, filename rules, non-empty PNG, directory creation,
  existing-file skip, renderer interaction, and filesystem/render failure mapping
- Golden comparison framework is in place (non-brittle; optional references)
- Real PNG generation exercised in tests and locally
- Physical scan of `9780064400558.png` decoded to Charlotte’s Web as expected
- PyInstaller one-file build completes; build script display is ASCII-safe on
  Windows cp1252 consoles

### Future Enhancements

Intentionally deferred:

- SVG (or other vector) output
- QR code renderer via `BarcodeSymbology.QR`
- Code128 support via `BarcodeSymbology.CODE128`
- Overwrite / force-regenerate option wired through settings
- Multiple output sizes or print-specific presets
- Checked-in golden PNGs once rendering is frozen for a release

### Related Features

- **FDR-001 — ISBN Validation Engine** (Feature 1): validates/normalizes ISBNs
  before generation; this engine consumes validated books only
- **Batch Processing Engine** (upcoming): will call
  `BarcodeGenerationService` for each book rather than owning rendering itself
