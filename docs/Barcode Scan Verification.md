# Manual barcode scan verification

Developer checklist for confirming that generated EAN-13 PNG files scan back
to the expected ISBN. Use this after changing renderer settings, dependencies,
or golden reference images.

## Expected result

For a book with ISBN-13 `978-0-06-440055-8` (Charlotte's Web sample):

| Field | Expected value |
|-------|----------------|
| Normalized ISBN / EAN-13 payload | `9780064400558` |
| Output filename | `9780064400558.png` |
| Scanner / phone decode | **`9780064400558`** (13 digits, no hyphens) |

Any other decode (truncated digits, ISBN-10, UPC-A without leading `9`, or a
different number) means the image is not acceptable for classroom labels.

## Generate a sample barcode

From `barcode_generator/`:

```powershell
python -c "
from classroom_library_label_maker.config import load_application_settings
from classroom_library_label_maker.models import Book
from classroom_library_label_maker.services import BarcodeGenerationService

settings = load_application_settings()
book = Book(
    isbn='978-0-06-440055-8',
    title=\"Charlotte's Web\",
    author='E. B. White',
    copies=1,
)
result = BarcodeGenerationService(settings).generate_for_book(book)
print(result.status, result.output_path)
"
```

Open the printed path (default: `output/barcodes/9780064400558.png`).

## Scan with a phone

1. Install a barcode scanner app that supports **EAN-13** (many “QR code”
   apps also read linear barcodes; confirm EAN-13 is enabled).
2. Display the PNG at 100% zoom on a bright screen, or print it at label size.
3. Scan the bars (not the human-readable digits under the bars).
4. Confirm the app reports **`9780064400558`**.

Tips:

- Prefer a dark-on-light image with intact quiet zones (white margins).
- If the phone struggles on-screen, print the PNG and scan the paper copy.
- Avoid heavy compression or screenshot cropping that clips the quiet zone.

## Scan with a hardware barcode scanner

1. Print `9780064400558.png` (laser/inkjet is fine for smoke tests).
2. Configure the scanner for EAN-13 if your model has symbology toggles.
3. Scan into Notepad or any text field.
4. Confirm the typed result is exactly **`9780064400558`**.

## Pass / fail

- **Pass** — decoded value equals the normalized ISBN-13 used as the filename.
- **Fail** — empty read, wrong length, or any other digit string.

Record failures with the renderer settings from `ApplicationSettings`
(`barcode_module_width`, `barcode_module_height`, `barcode_quiet_zone`,
`barcode_font_size`, `barcode_dpi`) before changing goldens.
