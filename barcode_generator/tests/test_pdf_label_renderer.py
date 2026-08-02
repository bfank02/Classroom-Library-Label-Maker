"""Tests for print-ready PDF label rendering."""

from __future__ import annotations

from pathlib import Path

from classroom_library_label_maker.label_templates import AVERY_5160
from classroom_library_label_maker.models import LabelContentOptions
from classroom_library_label_maker.rendering.barcode_renderer import (
    PythonBarcodeRenderer,
)
from classroom_library_label_maker.workbooks.label_sheet_target import LabelPlacement
from classroom_library_label_maker.workbooks.pdf_label_renderer import write_labels_pdf


def test_write_labels_pdf_creates_multipage_file(tmp_path: Path) -> None:
    png = tmp_path / "9780064400558.png"
    PythonBarcodeRenderer().render_to_file("9780064400558", png)

    placements = [
        LabelPlacement(
            page_number=1,
            row=0,
            column=0,
            title="Charlotte's Web",
            author="E. B. White",
            isbn="9780064400558",
            barcode_image_path=png,
            used_placeholder_barcode=False,
            content=LabelContentOptions(
                show_title=True,
                show_author=False,
                show_barcode=True,
            ),
        ),
        LabelPlacement(
            page_number=2,
            row=0,
            column=0,
            title="Matilda",
            author="Roald Dahl",
            isbn="9780140328721",
            barcode_image_path=png,
            used_placeholder_barcode=False,
            content=LabelContentOptions(
                show_title=True,
                show_author=False,
                show_barcode=True,
            ),
        ),
    ]
    out = tmp_path / "labels.pdf"
    written = write_labels_pdf(placements, AVERY_5160, out)
    assert written == out.resolve()
    assert out.is_file()
    assert out.stat().st_size > 1000
    assert out.read_bytes()[:4] == b"%PDF"


def test_long_title_stays_inside_label_band(tmp_path: Path) -> None:
    """Long titles must wrap/clip inside the label, not spill into the next column."""
    from PIL import Image, ImageDraw

    from classroom_library_label_maker.constants import EXCEL_BARCODE_PRINT_DPI
    from classroom_library_label_maker.workbooks import pdf_label_renderer as pdf_mod

    png = tmp_path / "9780689711817.png"
    PythonBarcodeRenderer().render_to_file("9780689711817", png)
    long_title = "From the Mixed-up Files of Mrs Basil E Frankweiler"

    placement = LabelPlacement(
        page_number=1,
        row=0,
        column=0,
        title=long_title,
        author="E. L. Konigsburg",
        isbn="9780689711817",
        barcode_image_path=png,
        used_placeholder_barcode=False,
        content=LabelContentOptions(
            show_title=True,
            show_author=False,
            show_barcode=True,
        ),
    )

    # Render one page in-memory the same way write_labels_pdf does.
    dpi = EXCEL_BARCODE_PRINT_DPI
    page = Image.new(
        "RGB",
        (
            int(round(AVERY_5160.page_width * dpi)),
            int(round(AVERY_5160.page_height * dpi)),
        ),
        color=(255, 255, 255),
    )
    draw = ImageDraw.Draw(page)
    from classroom_library_label_maker.rendering.title_fitter import (
        DEFAULT_TITLE_SIZE_PT,
        load_title_font,
    )

    font_title = load_title_font(bold=True, size_pt=DEFAULT_TITLE_SIZE_PT, dpi=dpi)
    font_body = load_title_font(bold=False, size_pt=8.0, dpi=dpi)
    pdf_mod._draw_label(
        page,
        draw,
        placement,
        template=AVERY_5160,
        dpi=dpi,
        font_title=font_title,
        font_body=font_body,
    )

    # Right edge of column-0 label, plus a thin strip into the horizontal gap /
    # next label — must stay white (no spilled title ink).
    label_right = AVERY_5160.left_margin + AVERY_5160.label_width
    gap_x = int(round((label_right + AVERY_5160.horizontal_gap / 2.0) * dpi))
    # Title+Barcode: title occupies 3 of 8 worksheet rows.
    title_band_bottom = int(
        round((AVERY_5160.top_margin + AVERY_5160.label_height * (3 / 8)) * dpi)
    )
    ink = 0
    for y in range(0, title_band_bottom + 4):
        pixel = page.getpixel((gap_x, y))
        if pixel[0] < 250 or pixel[1] < 250 or pixel[2] < 250:
            ink += 1
    assert ink == 0
