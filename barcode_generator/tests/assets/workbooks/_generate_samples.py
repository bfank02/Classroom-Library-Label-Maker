"""Generate small sample workbooks for Excel import tests."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parent


def save(name: str, rows: list[list[object | None]], sheet: str = "Books") -> Path:
    workbook = Workbook()
    worksheet = workbook.active
    assert worksheet is not None
    worksheet.title = sheet
    for row in rows:
        worksheet.append(row)
    path = ROOT / name
    workbook.save(path)
    print(f"wrote {path}")
    return path


def main() -> None:
    headers = ["ISBN", "Title", "Author", "Copies"]
    save(
        "valid_books.xlsx",
        [
            headers,
            ["9780064400558", "Charlotte's Web", "E. B. White", 1],
            ["9780060256654", "The Giving Tree", "Shel Silverstein", 2],
        ],
    )
    save("empty_books.xlsx", [headers])
    save(
        "blank_rows.xlsx",
        [
            headers,
            ["9780064400558", "Charlotte's Web", "E. B. White", 1],
            [None, None, None, None],
            ["", "", "", ""],
            ["9780060256654", "The Giving Tree", "Shel Silverstein", 1],
        ],
    )
    save(
        "missing_optional_copies.xlsx",
        [
            headers,
            ["9780064400558", "Charlotte's Web", "E. B. White", None],
        ],
    )
    save(
        "malformed_rows.xlsx",
        [
            headers,
            ["9780064400558", "Charlotte's Web", "E. B. White", 1],
            [None, "No ISBN", "Author", 1],
            ["9780060256654", None, "Shel Silverstein", 1],
            ["9780140328721", "Title", None, 1],
            ["9780142410370", "Good Book", "Author", "abc"],
            ["9780142410387", "Another", "Author", 0],
        ],
    )
    save(
        "wrong_sheet.xlsx",
        [
            headers,
            ["9780064400558", "A", "B", 1],
        ],
        sheet="Other",
    )
    # Missing required header column
    save(
        "missing_columns.xlsx",
        [
            ["ISBN", "Title", "Copies"],
            ["9780064400558", "Charlotte's Web", 1],
        ],
    )
    (ROOT / "not_a_workbook.xlsx").write_text("this is not excel", encoding="utf-8")
    print("done")


if __name__ == "__main__":
    main()
