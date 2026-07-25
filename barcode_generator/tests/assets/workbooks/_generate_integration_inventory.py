"""Generate the canonical integration-test inventory workbook.

Run from ``barcode_generator/``::

    python tests/assets/workbooks/_generate_integration_inventory.py
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from classroom_library_label_maker.services.isbn_validator import IsbnValidator

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "integration_inventory.xlsx"

# Realistic classics first; remaining rows use synthetic valid ISBN-13s.
_CLASSICS: list[tuple[str, str, str, int]] = [
    ("9780064400558", "Charlotte's Web", "E. B. White", 1),
    ("9780060256654", "The Giving Tree", "Shel Silverstein", 2),
    ("9780140328721", "Matilda", "Roald Dahl", 1),
]

# Avery 5160 holds 30 labels/page; 31 books forces a second page.
_TOTAL_BOOKS = 31


def _synthetic_isbn(index: int, validator: IsbnValidator) -> str:
    """Return a valid ISBN-13 for synthetic row ``index`` (0-based among synthetics)."""
    body = f"978{index:09d}"
    return body + validator.compute_check_digit(body)


def build_rows() -> list[list[object]]:
    """Return header + data rows for the integration inventory."""
    validator = IsbnValidator()
    rows: list[list[object]] = [["ISBN", "Title", "Author", "Copies"]]
    rows.extend([list(row) for row in _CLASSICS])

    used = {isbn for isbn, *_ in _CLASSICS}
    synthetic_index = 0
    while len(rows) - 1 < _TOTAL_BOOKS:
        isbn = _synthetic_isbn(synthetic_index, validator)
        synthetic_index += 1
        if isbn in used:
            continue
        assert validator.is_valid(isbn), isbn
        used.add(isbn)
        n = len(rows)  # 1-based display index among data rows about to add
        rows.append([isbn, f"Classroom Book {n}", f"Author {n}", 1])
    return rows


def main() -> None:
    rows = build_rows()
    assert len(rows) == _TOTAL_BOOKS + 1

    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Books"
    for row in rows:
        sheet.append(row)
    workbook.save(OUTPUT)
    print(f"wrote {OUTPUT} ({_TOTAL_BOOKS} books)")


if __name__ == "__main__":
    main()
