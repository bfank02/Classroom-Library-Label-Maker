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

For a larger **manual QA / demo** inventory (~190 books with blank ISBNs,
duplicates, and ambiguous titles), use
`samples/Teacher Demo Library.xlsx`. With **Look up missing ISBNs** enabled,
status advances as `Looking up missing ISBNs... (n of total)`.

**Optional but recommended for large batches:** set a Google Cloud API key
restricted to the Books API before launching:

```bash
export GOOGLE_BOOKS_API_KEY="your-key"
```

The app works without a key (anonymous mode, slower pacing). With a key,
startup logs `Google Books authentication: Enabled` and enrichment uses
faster authenticated pacing while still backing off on rate limits. Never
commit or share your key.

## 2. Open the app

Launch Classroom Library Label Maker, then choose:

1. **Inventory workbook** — your book list (or the sample file).
2. **Barcode folder** — any empty folder where barcode images can be saved.
3. **Label workbook** — where to save the printable labels file (default name
   `library_labels.xlsx`).
4. **Label template** — leave **Avery 5160** selected unless you use a
   different sheet.

After the first successful selection, the **barcode folder** and **label
workbook** path are remembered for next time. Change them anytime with Browse.

## 3. Generate labels

Click **Generate Labels**.

If books still need ISBN choices, the **Review ISBN Matches** wizard appears
so you can pick a catalog match or skip. Leave **Save updated inventory
workbook when review is complete** checked to write a new
`Inventory (Updated ISBNs).xlsx` next to your original inventory (your
original file is never changed).

- Green status ending in **Ready to print** means the label workbook is ready.
- Amber status saying **review before printing** means the file was created,
  but some labels need attention (for example a missing barcode).
- When an updated inventory was written, the status also lists both saved
  workbooks under **Generation Complete**.

## 4. Print from Excel

1. Open the **label workbook** in Excel.
2. Load Avery 5160 (or matching) label sheets in your printer.
3. Use **File → Print**. Page setup is already applied for the selected
   template — you usually do not need to change margins.

The app creates the label file; printing happens in Excel.
