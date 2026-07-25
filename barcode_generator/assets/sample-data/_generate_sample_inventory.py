"""Generate the teacher-facing sample inventory workbook.

Writes the same file to:

* ``barcode_generator/assets/sample-data/Sample Books.xlsx`` (bundled with the app)
* ``samples/Sample Books.xlsx`` (repo root, for browsing from docs)

Run from ``barcode_generator/``::

    python assets/sample-data/_generate_sample_inventory.py
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from classroom_library_label_maker.constants import (
    DEFAULT_WORKBOOK_COLUMN_AUTHOR,
    DEFAULT_WORKBOOK_COLUMN_COPIES,
    DEFAULT_WORKBOOK_COLUMN_ISBN,
    DEFAULT_WORKBOOK_COLUMN_TITLE,
    DEFAULT_WORKBOOK_SHEET_NAME,
)
from classroom_library_label_maker.services.isbn_validator import IsbnValidator

PACKAGE_ROOT = Path(__file__).resolve().parents[2]  # barcode_generator/
REPO_ROOT = PACKAGE_ROOT.parent
ASSET_OUTPUT = Path(__file__).resolve().parent / "Sample Books.xlsx"
SAMPLES_OUTPUT = REPO_ROOT / "samples" / "Sample Books.xlsx"

# Realistic classroom titles with valid ISBN-13s (verified at generate time).
_BOOKS: list[tuple[str, str, str, int]] = [
    # Fiction
    ("9780064400558", "Charlotte's Web", "E. B. White", 2),
    ("9780060256654", "The Giving Tree", "Shel Silverstein", 1),
    ("9780140328721", "Matilda", "Roald Dahl", 3),
    ("9780439708180", "Harry Potter and the Sorcerer's Stone", "J. K. Rowling", 2),
    ("9780142410349", "The Tale of Despereaux", "Kate DiCamillo", 1),
    ("9780394800011", "The Cat in the Hat", "Dr. Seuss", 4),
    ("9780064403375", "Number the Stars", "Lois Lowry", 1),
    ("9780439358064", "Harry Potter and the Order of the Phoenix", "J. K. Rowling", 1),
    ("9780142407332", "Because of Winn-Dixie", "Kate DiCamillo", 2),
    ("9780399226908", "The Very Hungry Caterpillar", "Eric Carle", 2),
    ("9780064404778", "The Lion, the Witch and the Wardrobe", "C. S. Lewis", 1),
    ("9780394800165", "Green Eggs and Ham", "Dr. Seuss", 3),
    # Nonfiction / informational
    ("9780545685153", "Who Was Rosa Parks?", "Yona Zeldis McDonough", 1),
    ("9780448459714", "Who Was Albert Einstein?", "Jess Brallier", 1),
    ("9781338236668", "I Survived the American Revolution, 1776", "Lauren Tarshis", 2),
    ("9781426313714", "National Geographic Kids: Weather", "Kathy Furgang", 1),
    ("9780064450157", "From Seed to Plant", "Gail Gibbons", 3),
    ("9780394839127", "Oh, the Places You'll Go!", "Dr. Seuss", 1),
]


def build_rows(validator: IsbnValidator) -> list[list[object]]:
    """Return header + data rows; assert every ISBN is valid."""
    rows: list[list[object]] = [
        [
            DEFAULT_WORKBOOK_COLUMN_ISBN,
            DEFAULT_WORKBOOK_COLUMN_TITLE,
            DEFAULT_WORKBOOK_COLUMN_AUTHOR,
            DEFAULT_WORKBOOK_COLUMN_COPIES,
        ]
    ]
    for isbn, title, author, copies in _BOOKS:
        assert validator.is_valid(isbn), f"invalid sample ISBN: {isbn}"
        rows.append([isbn, title, author, copies])
    return rows


def write_workbook(path: Path, rows: list[list[object]]) -> None:
    """Write ``rows`` to an Excel workbook at ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = DEFAULT_WORKBOOK_SHEET_NAME
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def main() -> None:
    validator = IsbnValidator()
    rows = build_rows(validator)
    book_count = len(rows) - 1
    assert 15 <= book_count <= 20, book_count

    write_workbook(ASSET_OUTPUT, rows)
    write_workbook(SAMPLES_OUTPUT, rows)
    print(f"wrote {ASSET_OUTPUT} ({book_count} books)")
    print(f"wrote {SAMPLES_OUTPUT} ({book_count} books)")


if __name__ == "__main__":
    main()
