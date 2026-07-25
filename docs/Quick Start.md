# Classroom Library Label Maker — Quick Start

Create printable barcode labels from an Excel list of books.

## 1. Prepare your book list

Open Excel and create a workbook with a sheet named **Books**.

Row 1 must use these column headers (exact spelling):

| ISBN | Title | Author | Copies |
|------|-------|--------|--------|

- Put one book per row under the headers.
- **ISBN** must be a valid 13-digit ISBN.
- **Copies** is how many labels to print for that title (for example `1`, `2`, or `3`).

A ready-made example is included: `samples/Sample Books.xlsx` (also under
`barcode_generator/assets/sample-data/`).

## 2. Open the app

Launch Classroom Library Label Maker, then choose:

1. **Inventory workbook** — your book list (or the sample file).
2. **Barcode folder** — any empty folder where barcode images can be saved.
3. **Label workbook** — where to save the printable labels file (default name
   `library_labels.xlsx`).
4. **Label template** — leave **Avery 5160** selected unless you use a
   different sheet.

## 3. Generate labels

Click **Generate Labels**.

- Green status ending in **Ready to print** means the label workbook is ready.
- Amber status saying **review before printing** means the file was created,
  but some labels need attention (for example a missing barcode).

## 4. Print from Excel

1. Open the **label workbook** in Excel.
2. Load Avery 5160 (or matching) label sheets in your printer.
3. Use **File → Print**. Page setup is already applied for the selected
   template — you usually do not need to change margins.

The app creates the label file; printing happens in Excel.
