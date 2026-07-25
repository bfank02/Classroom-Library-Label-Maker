"""Tests for print-ready workbook presentation (openpyxl adapters)."""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from classroom_library_label_maker.label_templates import AVERY_5160
from classroom_library_label_maker.metadata import APP_AUTHOR, APP_NAME
from classroom_library_label_maker.workbooks.label_sheet_target import LabelPlacement
from classroom_library_label_maker.workbooks.openpyxl_label_sheet_target import (
    LABEL_SHEET_PREFIX,
    OpenPyxlLabelSheetTarget,
)
from classroom_library_label_maker.workbooks.openpyxl_workbook_writer import (
    OpenPyxlWorkbookWriter,
)
from classroom_library_label_maker.workbooks.workbook_presentation import (
    _PAPERSIZE_LETTER,
    apply_workbook_properties,
    apply_worksheet_presentation,
)


def test_sheet_naming_consistency() -> None:
    """Label sheets should use the Labels N naming convention."""
    target = OpenPyxlLabelSheetTarget()
    target.begin_page(1, template=AVERY_5160)
    target.begin_page(2, template=AVERY_5160)
    assert target.workbook.sheetnames == [
        f"{LABEL_SHEET_PREFIX}1",
        f"{LABEL_SHEET_PREFIX}2",
    ]


def test_worksheet_presentation_and_page_setup() -> None:
    """Sheets should hide gridlines and use template-derived page setup."""
    target = OpenPyxlLabelSheetTarget()
    target.begin_page(1, template=AVERY_5160)
    sheet = target.workbook[f"{LABEL_SHEET_PREFIX}1"]

    assert sheet.sheet_view.showGridLines is False
    assert sheet.sheet_view.zoomScale == 100
    assert sheet.page_setup.orientation == "portrait"
    assert sheet.page_setup.paperSize == _PAPERSIZE_LETTER
    assert sheet.page_setup.fitToPage is True
    assert sheet.page_setup.fitToWidth == 1
    assert sheet.page_setup.fitToHeight == 1

    assert sheet.page_margins.left == AVERY_5160.left_margin
    assert sheet.page_margins.top == AVERY_5160.top_margin
    expected_right = (
        AVERY_5160.page_width - AVERY_5160.left_margin - AVERY_5160.printable_width
    )
    expected_bottom = (
        AVERY_5160.page_height - AVERY_5160.top_margin - AVERY_5160.printable_height
    )
    assert abs(sheet.page_margins.right - expected_right) < 1e-9
    assert abs(sheet.page_margins.bottom - expected_bottom) < 1e-9

    assert sheet.print_area is not None
    assert "A1" in sheet.print_area.replace("$", "")
    assert "C40" in sheet.print_area.replace("$", "")
    assert sheet.print_options.horizontalCentered is True


def test_workbook_properties_and_active_sheet(tmp_path: Path) -> None:
    """Saved workbooks should carry document properties and activate Labels 1."""
    writer = OpenPyxlWorkbookWriter()
    writer.create_workbook()
    target = writer.get_label_sheet_target()
    assert isinstance(target, OpenPyxlLabelSheetTarget)
    target.begin_page(1, template=AVERY_5160)
    target.begin_page(2, template=AVERY_5160)
    target.place_label(
        LabelPlacement(
            page_number=1,
            row=0,
            column=0,
            title="Short Title",
            author="Author",
            isbn="9780064400558",
            used_placeholder_barcode=True,
        )
    )

    out = tmp_path / "presented.xlsx"
    writer.save(out)
    writer.close()

    workbook = load_workbook(out)
    try:
        assert workbook.properties.title.startswith(APP_NAME)
        assert workbook.properties.creator == APP_AUTHOR
        assert "5160" in (workbook.properties.subject or "")
        assert workbook.active.title == f"{LABEL_SHEET_PREFIX}1"
        assert workbook.sheetnames[0] == f"{LABEL_SHEET_PREFIX}1"
    finally:
        workbook.close()


def test_label_formatting_wraps_long_titles() -> None:
    """Title cells should use wrapping centered alignment and title font."""
    target = OpenPyxlLabelSheetTarget()
    target.begin_page(1, template=AVERY_5160)
    long_title = (
        "An Extremely Long Classroom Library Book Title That Must Wrap "
        "Within The Label Without Overlapping Neighbors"
    )
    target.place_label(
        LabelPlacement(
            page_number=1,
            row=0,
            column=0,
            title=long_title,
            author="Author Name",
            isbn="9780064400558",
            used_placeholder_barcode=True,
        )
    )
    sheet = target.workbook[f"{LABEL_SHEET_PREFIX}1"]
    title_cell = sheet.cell(1, 1)
    assert title_cell.value == long_title
    assert title_cell.alignment.wrap_text is True
    assert title_cell.alignment.horizontal == "center"
    assert title_cell.font.bold is True
    assert sheet.cell(2, 1).alignment.wrap_text is True
    assert sheet.cell(3, 1).value == "9780064400558"


def test_barcode_image_fits_within_label_slot(tmp_path: Path) -> None:
    """Barcode drawings must be short enough not to cover the next label's text."""
    import zipfile
    from xml.etree import ElementTree as ET

    from classroom_library_label_maker.rendering.barcode_renderer import (
        PythonBarcodeRenderer,
    )
    from classroom_library_label_maker.workbooks.openpyxl_label_sheet_target import (
        _LABEL_ROW_FRACTIONS,
    )
    from classroom_library_label_maker.workbooks.openpyxl_workbook_writer import (
        OpenPyxlWorkbookWriter,
    )

    png = tmp_path / "9780064400558.png"
    PythonBarcodeRenderer().render_to_file("9780064400558", png)

    writer = OpenPyxlWorkbookWriter()
    writer.create_workbook()
    target = writer.get_label_sheet_target()
    assert isinstance(target, OpenPyxlLabelSheetTarget)
    target.begin_page(1, template=AVERY_5160)
    target.place_label(
        LabelPlacement(
            page_number=1,
            row=0,
            column=0,
            title="Charlotte's Web",
            author="E. B. White",
            isbn="9780064400558",
            barcode_image_path=png,
            used_placeholder_barcode=False,
        )
    )
    target.place_label(
        LabelPlacement(
            page_number=1,
            row=1,
            column=0,
            title="The Giving Tree",
            author="Shel Silverstein",
            isbn="9780060256654",
            used_placeholder_barcode=True,
        )
    )

    out = tmp_path / "sized.xlsx"
    writer.save(out)
    writer.close()

    workbook = load_workbook(out)
    try:
        sheet = workbook[f"{LABEL_SHEET_PREFIX}1"]
        assert sheet.cell(1, 1).value == "Charlotte's Web"
        assert sheet.cell(5, 1).value == "The Giving Tree"
        assert sheet.row_dimensions[4].height > sheet.row_dimensions[1].height
    finally:
        workbook.close()

    with zipfile.ZipFile(out) as archive:
        drawing = next(n for n in archive.namelist() if n.startswith("xl/drawings/drawing"))
        root = ET.fromstring(archive.read(drawing))
    ns = {
        "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
    }
    ext = root.find(".//xdr:ext", ns)
    assert ext is not None
    # EMUs: 914400 per inch. Barcode must stay within its band (~0.55").
    height_in = int(ext.attrib["cy"]) / 914400.0
    max_height_in = AVERY_5160.label_height * _LABEL_ROW_FRACTIONS[3] * 0.95
    assert height_in <= max_height_in


def test_apply_presentation_helpers_are_idempotent() -> None:
    """Re-applying presentation helpers should not raise."""
    target = OpenPyxlLabelSheetTarget()
    target.begin_page(1, template=AVERY_5160)
    sheet = target.workbook[f"{LABEL_SHEET_PREFIX}1"]
    apply_worksheet_presentation(sheet, AVERY_5160)
    apply_workbook_properties(target.workbook, template=AVERY_5160)
    assert sheet.print_area is not None
    assert "C40" in sheet.print_area.replace("$", "")
