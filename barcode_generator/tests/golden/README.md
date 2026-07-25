# Golden barcode images

This directory holds **known-good reference barcode PNGs** used by optional
regression checks for the Barcode Generation Engine.

## Purpose

Golden images capture the *intended* look of rendered EAN-13 barcodes for a
small set of stable ISBNs. They exist so intentional rendering changes are
reviewed deliberately, and accidental visual regressions are easier to spot.

They are **not** a pixel-perfect lock on every PNG byte. Antialiasing, font
hinting, and Pillow/python-barcode internals can shift individual pixels across
environments. Comparisons therefore use structural and perceptual tolerances
(see `helpers.py`).

## Layout

```
tests/golden/
├── README.md          # This file
├── helpers.py         # Comparison helpers (non-brittle)
├── .gitkeep           # Keeps the directory tracked when empty
└── *.png              # Optional reference images (ISBN stem, e.g. 9780064400558.png)
```

Reference files are optional. When no matching golden PNG is present, golden
tests skip rather than fail CI.

## Comparison philosophy

Do **not** assert byte-identical PNG files.

Preferred checks (implemented in `helpers.py`):

1. **Structural** — valid PNG, non-empty, dimensions within a small tolerance
2. **Perceptual** — average-hash Hamming distance under a generous threshold

Avoid:

- Exact `file.read_bytes()` equality
- Exact CRC / compressed-stream equality
- Zero-tolerance pixel diffs

## Updating golden images

Update goldens **only** when rendering behavior changes on purpose
(geometry, DPI, quiet zone, font, symbology options, etc.).

1. Confirm the new look with a real scanner (see Architecture /
   README “Manual barcode verification”).
2. Generate a fresh PNG with the production defaults, for example:

   ```powershell
   cd barcode_generator
   python -c "
   from classroom_library_label_maker.config import load_application_settings
   from classroom_library_label_maker.models import Book
   from classroom_library_label_maker.services import BarcodeGenerationService
   settings = load_application_settings()
   book = Book(isbn='9780064400558', title='Charlotte''s Web', author='E. B. White')
   result = BarcodeGenerationService(settings).generate_for_book(book)
   print(result.output_path)
   "
   ```

3. Copy the approved file into this directory using the normalized ISBN name:

   ```powershell
   Copy-Item output\barcodes\9780064400558.png tests\golden\9780064400558.png
   ```

4. Or set `UPDATE_GOLDEN=1` when running the golden suite (writes missing /
   outdated references from freshly generated images — review the diff before
   committing).

5. Commit the updated PNG(s) with a message that explains *why* rendering
   changed (not only that goldens were refreshed).

## CI policy

- Golden helpers and framework unit tests always run.
- Comparisons against missing reference files **skip**.
- Do not turn golden checks into flaky pixel-perfect gates.
