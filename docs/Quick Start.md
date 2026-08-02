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

**Optional but recommended for large batches:** configure a Google Cloud API key
restricted to the Books API.

Shell / development (current terminal only)::

```bash
export GOOGLE_BOOKS_API_KEY="your-key"
```

**Packaged macOS / Windows app (Finder / Dock):** shell exports are **not**
visible to the app. Install the key into the per-user config file instead::

```bash
cd barcode_generator
export GOOGLE_BOOKS_API_KEY="your-key"
python scripts/install_google_books_api_key.py
```

Then fully quit and relaunch the app. Startup should log
`Google Books authentication: Enabled`. If logs still say anonymous mode, the
key is not reaching the app.

## 2. Open the app

Launch Classroom Library Label Maker. The Home screen shows a short header,
then three sections from top to bottom:

**Files**

1. **Inventory Workbook** — your book list (or the sample file).
2. **Barcode Folder** — any empty folder where barcode images can be saved.
3. **Label Folder** — the folder where the printable labels file is saved.
4. **Label File Name** — the workbook name (default `library_labels.xlsx`).
   Click the field to rename; the `.xlsx` extension stays visible.

**Options**

5. **Label template** — leave **Avery 5160** selected unless you use a
   different sheet.
6. Label contents and **Look up missing ISBNs automatically** as needed.

**Actions**

Status messages and **Generate Labels** live here (not in Files).

After the first successful selection, the inventory workbook, barcode folder,
label folder, and label file name are remembered for next time. Change a folder
anytime with Browse (Browse for Label Folder keeps your file name). Edit the
file name directly without opening a dialog. The muted version label in the
lower-right corner is for support if you need to report which build you have.

## 3. Generate labels

In **Actions**, click **Generate Labels**.

If books still need ISBN choices, the **Review ISBN Matches** wizard appears.
Choose a catalog match (it highlights, then moves on after a brief pause),
enter an ISBN yourself under **Enter ISBN Manually** (ISBN-10 or ISBN-13), or
click **Don't Generate Label** when you intentionally want no label for that
book (you'll see **✓ Label will not be generated**, then move on after a brief
pause). Use **Previous** to go back; your prior choice (or an unfinished manual
entry) is restored. On the last book, **Finish Review** replaces **Don't
Generate Label** once you have selected, entered, or opted out. Leave **Save
updated inventory workbook when review is complete** checked to write a new
`Inventory (Updated ISBNs).xlsx` next to your original inventory (your
original file is never changed). Skipped books stay in that inventory with
blank ISBNs and never appear on labels.

When generation finishes, the main window shows a **✔ Ready to Print** page
(not a dialog): label/page counts, optional ISBN and review totals, the
created file names, and actions to **Open Label Workbook**, **Open Updated
Inventory** (when written), or **Done**. **Done** returns to the Home screen
with your Files settings preserved so you can generate again.

- A clean Ready to Print page means the label workbook is ready.
- If the summary mentions **review before printing**, the file was created
  but some labels need attention (for example a missing barcode).
- Updated inventory appears under **Files Created** only when one was written.

## 4. Print from Excel

1. Open the **label workbook** in Excel.
2. Load Avery 5160 (or matching) label sheets in your printer.
3. Use **File → Print**. Page setup is already applied for the selected
   template — you usually do not need to change margins.

The app creates the label file; printing happens in Excel.
