"""Tests for the label layout engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from classroom_library_label_maker.exceptions import ConfigurationError, LabelLayoutError
from classroom_library_label_maker.label_templates import (
    AVERY_5160,
    LabelTemplateSpec,
    PageOrientation,
    PageSize,
    TemplateRegistry,
)
from classroom_library_label_maker.models import ApplicationSettings, Book
from classroom_library_label_maker.services.label_layout_service import (
    LabelLayoutService,
)
from classroom_library_label_maker.workbooks import InMemoryLabelSheetTarget


def _book(isbn: str, title: str = "Title", author: str = "Author") -> Book:
    return Book(isbn=isbn, title=title, author=author, copies=1)


def _books(count: int) -> list[Book]:
    return [
        _book(f"97800000000{i:02d}"[:13].ljust(13, "0"), title=f"Book {i}")
        for i in range(count)
    ]


@pytest.fixture
def layout_service(app_settings: ApplicationSettings) -> LabelLayoutService:
    return LabelLayoutService(app_settings)


def test_single_page_layout(layout_service: LabelLayoutService) -> None:
    """Books that fit on one page should create a single page."""
    target = InMemoryLabelSheetTarget()
    books = _books(3)
    result = layout_service.layout_books(books, target)

    assert result.pages_created == 1
    assert result.labels_placed == 3
    assert result.empty_labels_remaining_on_last_page == 27
    assert result.template_id == "avery-5160"
    assert len(target.pages) == 1
    assert target.placements[0].row == 0 and target.placements[0].column == 0
    assert target.placements[1].column == 1
    assert target.placements[2].column == 2


def test_multiple_pages_and_transitions(layout_service: LabelLayoutService) -> None:
    """Overflow beyond labels_per_page should create additional pages."""
    target = InMemoryLabelSheetTarget()
    books = _books(31)  # Avery 5160 holds 30
    result = layout_service.layout_books(books, target)

    assert result.pages_created == 2
    assert result.labels_placed == 31
    assert result.empty_labels_remaining_on_last_page == 29
    assert target.pages == [1, 2]
    assert target.placements[29].page_number == 1
    assert target.placements[30].page_number == 2
    assert target.placements[30].row == 0
    assert target.placements[30].column == 0


def test_partially_filled_last_page(layout_service: LabelLayoutService) -> None:
    """Statistics should report unused slots on the last page."""
    target = InMemoryLabelSheetTarget()
    result = layout_service.layout_books(_books(35), target)

    assert result.pages_created == 2
    assert result.labels_placed == 35
    assert result.empty_labels_remaining_on_last_page == 25


def test_exact_full_page_has_zero_empty_slots(
    layout_service: LabelLayoutService,
) -> None:
    """A completely full final page should report zero empty remaining slots."""
    target = InMemoryLabelSheetTarget()
    result = layout_service.layout_books(_books(30), target)
    assert result.pages_created == 1
    assert result.empty_labels_remaining_on_last_page == 0


def test_empty_collection(layout_service: LabelLayoutService) -> None:
    """Empty input should create no pages and place no labels."""
    target = InMemoryLabelSheetTarget()
    result = layout_service.layout_books([], target)
    assert result.pages_created == 0
    assert result.labels_placed == 0
    assert result.empty_labels_remaining_on_last_page == 0
    assert target.placements == []


def test_copies_expand_to_multiple_labels(layout_service: LabelLayoutService) -> None:
    """Book.copies should produce that many physical labels for the same book."""
    target = InMemoryLabelSheetTarget()
    books = [
        Book(isbn="9780064400558", title="Charlotte's Web", author="E. B. White", copies=3),
        Book(isbn="9780140328721", title="Matilda", author="Roald Dahl", copies=2),
    ]
    result = layout_service.layout_books(books, target)

    assert result.labels_placed == 5
    assert result.pages_created == 1
    assert result.empty_labels_remaining_on_last_page == 25
    assert [p.isbn for p in target.placements] == [
        "9780064400558",
        "9780064400558",
        "9780064400558",
        "9780140328721",
        "9780140328721",
    ]


def test_different_template_lookup(app_settings: ApplicationSettings) -> None:
    """Explicit alternate templates should drive capacity and placement."""
    tiny = LabelTemplateSpec(
        template_id="test-2up",
        template_name="Test 2-up",
        vendor="Test",
        product_number="T2",
        description="Two labels for tests",
        page_size=PageSize.LETTER,
        orientation=PageOrientation.PORTRAIT,
        page_width=8.5,
        page_height=11.0,
        rows=1,
        columns=2,
        label_width=2.0,
        label_height=1.0,
        top_margin=0.5,
        left_margin=0.5,
        horizontal_gap=0.25,
        vertical_gap=0.0,
    )
    registry = TemplateRegistry()
    registry.register(AVERY_5160)
    registry.register(tiny)
    service = LabelLayoutService(app_settings, registry=registry)
    target = InMemoryLabelSheetTarget()

    result = service.layout_books(_books(3), target, template=tiny)

    assert result.template_id == "test-2up"
    assert result.pages_created == 2
    assert result.labels_placed == 3
    assert result.empty_labels_remaining_on_last_page == 1
    assert target.placements[2].page_number == 2


def test_settings_template_lookup(app_settings: ApplicationSettings) -> None:
    """Unknown configured template ids should raise ConfigurationError."""
    app_settings.label_template_id = "missing-template"
    service = LabelLayoutService(app_settings)
    with pytest.raises(ConfigurationError, match="Unknown label template"):
        service.layout_books([_book("9780064400558")], InMemoryLabelSheetTarget())


def test_placeholder_barcode_handling(
    layout_service: LabelLayoutService,
    tmp_path: Path,
) -> None:
    """Missing barcode images should use placeholders and collect warnings."""
    target = InMemoryLabelSheetTarget()
    books = [
        _book("9780064400558", title="Has Image"),
        _book("9780060256654", title="Missing Map"),
        _book("9780140328721", title="Missing File"),
    ]
    existing = tmp_path / "9780064400558.png"
    existing.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    missing_file = tmp_path / "gone.png"

    result = layout_service.layout_books(
        books,
        target,
        barcode_paths={
            "9780064400558": existing,
            "9780140328721": missing_file,
        },
    )

    assert result.labels_placed == 3
    assert len(result.warnings) == 2
    assert {w.code for w in result.warnings} == {
        "missing_barcode",
        "barcode_file_missing",
    }
    assert target.placements[0].used_placeholder_barcode is False
    assert target.placements[0].barcode_image_path == existing
    assert target.placements[1].used_placeholder_barcode is True
    assert target.placements[2].used_placeholder_barcode is True


def test_layout_statistics_in_result(layout_service: LabelLayoutService) -> None:
    """LabelLayoutResult should expose summary statistics via to_dict."""
    result = layout_service.layout_books(_books(5), InMemoryLabelSheetTarget())
    summary = result.to_dict()["summary"]
    assert summary["pages_created"] == 1
    assert summary["labels_placed"] == 5
    assert summary["empty_labels_remaining_on_last_page"] == 25
    assert summary["template_id"] == "avery-5160"
    assert summary["elapsed_seconds"] >= 0.0


def test_label_content_fields(layout_service: LabelLayoutService) -> None:
    """Placements should carry title, author, ISBN for clean centered labels."""
    target = InMemoryLabelSheetTarget()
    book = _book("9780064400558", title="Charlotte's Web", author="E. B. White")
    layout_service.layout_books([book], target)
    placement = target.placements[0]
    assert placement.title == "Charlotte's Web"
    assert placement.author == "E. B. White"
    assert placement.isbn == "9780064400558"


def test_target_failure_maps_to_label_layout_error(
    layout_service: LabelLayoutService,
) -> None:
    """Unexpected target failures should become LabelLayoutError."""

    class BrokenTarget:
        def begin_page(self, page_number: int, *, template: object) -> None:
            raise RuntimeError("boom")

        def place_label(self, placement: object) -> None:
            return None

    with pytest.raises(LabelLayoutError, match="Label layout failed"):
        layout_service.layout_books([_book("9780064400558")], BrokenTarget())


def test_openpyxl_target_places_without_saving(
    layout_service: LabelLayoutService,
    tmp_path: Path,
) -> None:
    """OpenPyxlLabelSheetTarget should create sheets and cells without save."""
    from classroom_library_label_maker.workbooks import OpenPyxlLabelSheetTarget

    barcode = tmp_path / "9780064400558.png"
    from PIL import Image as PILImage

    PILImage.new("RGB", (800, 200), color=(0, 0, 0)).save(barcode)
    target = OpenPyxlLabelSheetTarget()
    result = layout_service.layout_books(
        [_book("9780064400558", title="Demo", author="Author")],
        target,
        barcode_paths={"9780064400558": barcode},
    )
    assert result.labels_placed == 1
    assert "Labels 1" in target.workbook.sheetnames
    sheet = target.workbook["Labels 1"]
    assert sheet.cell(1, 1).value == "Demo"
    assert sheet.cell(3, 1).value == "Author"
    # Barcode slot is empty text when a PNG is present; ISBN is in the image.
    assert sheet.cell(4, 1).value in (None, "")
    assert len(sheet._images) == 1
