"""Tests for enrichment ReviewItem details in summaries and generation."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

from openpyxl import Workbook

from classroom_library_label_maker.config import load_application_settings
from classroom_library_label_maker.constants import DEFAULT_LABEL_TEMPLATE_ID
from classroom_library_label_maker.generation_summary import (
    cli_completion_lines,
    gui_completion_status,
)
from classroom_library_label_maker.models import (
    Book,
    BookEnrichmentResult,
    BookEnrichmentStatus,
    EnrichmentSummary,
    ReviewItem,
    WorkbookGenerationResult,
)
from classroom_library_label_maker.services.book_enrichment_service import (
    BookEnrichmentService,
)
from classroom_library_label_maker.services.workbook_generation_service import (
    WorkbookGenerationService,
)


class _ScriptedProvider:
    def __init__(self, by_title: dict[str, BookEnrichmentResult]) -> None:
        self._by_title = by_title
        self.calls = 0

    def enrich(self, book: Book) -> BookEnrichmentResult:
        self.calls += 1
        return self._by_title[book.title]


def _review_item(
    title: str,
    *,
    status: BookEnrichmentStatus = BookEnrichmentStatus.NOT_FOUND,
    message: str = "No ISBN found",
) -> ReviewItem:
    return ReviewItem(
        title=title,
        author="Author",
        status=status,
        message=message,
    )


def test_review_item_is_immutable() -> None:
    item = _review_item("A")
    try:
        item.title = "B"  # type: ignore[misc]
        raised = False
    except FrozenInstanceError:
        raised = True
    assert raised


def test_enrichment_summary_includes_review_items() -> None:
    items = (
        _review_item("One", status=BookEnrichmentStatus.AMBIGUOUS),
        _review_item("Two", status=BookEnrichmentStatus.ERROR, message="timeout"),
    )
    summary = EnrichmentSummary(
        enabled=True,
        isbns_found=3,
        review_items=items,
    )
    assert summary.needs_review_count == 2
    payload = summary.to_dict()
    assert payload["needs_review_count"] == 2
    assert payload["review_items"][0]["title"] == "One"
    assert payload["review_items"][0]["status"] == "ambiguous"
    assert payload["review_items"][1]["message"] == "timeout"


def test_gui_summary_shows_limited_review_items() -> None:
    items = tuple(
        _review_item(f"Book {i}", message=f"reason {i}") for i in range(1, 8)
    )
    result = WorkbookGenerationResult(
        books_imported=7,
        books_processed=7,
        labels_created=7,
        pages_created=1,
        barcodes_generated=0,
        output_path=Path("labels.xlsx"),
        enrichment=EnrichmentSummary(
            enabled=True,
            isbns_found=2,
            review_items=items,
        ),
        warnings=(),
    )
    text = gui_completion_status(result)
    assert "ISBN Lookup Summary" in text
    assert "✓ Found automatically: 2" in text
    assert "⚠ Needs Review: 7" in text
    assert "Book 1 — reason 1" in text
    assert "Book 5 — reason 5" in text
    assert "Book 6" not in text
    assert "...and 2 more." in text


def test_gui_summary_omits_block_when_no_review_items() -> None:
    result = WorkbookGenerationResult(
        books_imported=2,
        books_processed=2,
        labels_created=2,
        pages_created=1,
        barcodes_generated=2,
        output_path=Path("labels.xlsx"),
        enrichment=EnrichmentSummary(enabled=True, isbns_found=2, review_items=()),
    )
    text = gui_completion_status(result)
    assert "ISBN Lookup Summary" not in text
    assert "Needs Review" not in text
    assert text.startswith("Done —")


def test_cli_summary_lists_review_items() -> None:
    result = WorkbookGenerationResult(
        books_imported=2,
        books_processed=2,
        labels_created=2,
        pages_created=1,
        barcodes_generated=1,
        output_path=Path("labels.xlsx"),
        enrichment=EnrichmentSummary(
            enabled=True,
            books_looked_up=2,
            isbns_found=1,
            not_found=1,
            review_items=(
                _review_item("Missing Book", message="No ISBN found"),
            ),
        ),
    )
    lines = "\n".join(cli_completion_lines(result))
    assert "ISBN enrichment:" in lines
    assert "ISBN Lookup Summary" in lines
    assert "✓ Found automatically: 1" in lines
    assert "⚠ Needs Review: 1" in lines
    assert "Missing Book — No ISBN found" in lines


def test_generation_creates_review_items_for_attention_statuses(
    tmp_path: Path,
) -> None:
    wb_path = tmp_path / "books.xlsx"
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Books"
    ws.append(["ISBN", "Title", "Author", "Copies"])
    ws.append(["", "Ambiguous Book", "A Author", 1])
    ws.append(["", "Missing Book", "B Author", 1])
    ws.append(["", "Error Book", "C Author", 1])
    ws.append(["", "Found Book", "D Author", 1])
    wb.save(wb_path)

    barcodes = tmp_path / "barcodes"
    barcodes.mkdir()
    settings = load_application_settings(
        workbook_path=wb_path,
        barcode_output_directory=barcodes,
        label_template_id=DEFAULT_LABEL_TEMPLATE_ID,
        overwrite=True,
        lookup_missing_isbns=True,
    )
    provider = _ScriptedProvider(
        {
            "Ambiguous Book": BookEnrichmentResult(
                isbn="x",
                status=BookEnrichmentStatus.AMBIGUOUS,
                message="two hits",
            ),
            "Missing Book": BookEnrichmentResult(
                isbn="x",
                status=BookEnrichmentStatus.NOT_FOUND,
            ),
            "Error Book": BookEnrichmentResult(
                isbn="x",
                status=BookEnrichmentStatus.ERROR,
                message="timed out",
            ),
            "Found Book": BookEnrichmentResult(
                isbn="9780064400558",
                status=BookEnrichmentStatus.FOUND,
            ),
        }
    )
    result = WorkbookGenerationService(
        settings,
        enrichment=BookEnrichmentService(provider=provider),
    ).generate(workbook_path=wb_path, output_path=tmp_path / "out.xlsx")

    assert result.enrichment is not None
    assert result.enrichment.isbns_found == 1
    assert result.enrichment.needs_review_count == 3
    statuses = {item.status for item in result.enrichment.review_items}
    assert statuses == {
        BookEnrichmentStatus.AMBIGUOUS,
        BookEnrichmentStatus.NOT_FOUND,
        BookEnrichmentStatus.ERROR,
    }
    titles = {item.title for item in result.enrichment.review_items}
    assert "Found Book" not in titles
    assert "Ambiguous Book" in titles

    gui = gui_completion_status(result)
    assert "⚠ Needs Review: 3" in gui
    assert "Ambiguous Book — Multiple catalog matches" in gui
