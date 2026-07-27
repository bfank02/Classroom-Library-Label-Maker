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
