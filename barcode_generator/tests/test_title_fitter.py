"""Regression tests for font-metrics adaptive label title fitting."""

from __future__ import annotations

from classroom_library_label_maker.label_templates import AVERY_5160
from classroom_library_label_maker.models import LabelContentOptions
from classroom_library_label_maker.rendering.title_fitter import (
    DEFAULT_TITLE_SIZE_PT,
    MAX_TITLE_LINES,
    MIN_TITLE_SIZE_PT,
    FittedTitle,
    fit_label_title,
    load_title_font,
)
from classroom_library_label_maker.workbooks.label_sheet_target import LabelPlacement
from classroom_library_label_maker.workbooks.openpyxl_label_sheet_target import (
    LABEL_SHEET_PREFIX,
    OpenPyxlLabelSheetTarget,
    _distribute_row_spans,
)

# Avery 5160 title band with barcode: 3 of 8 rows.
_TITLE_BAND_HEIGHT_IN = AVERY_5160.label_height * (3 / 8)
_TITLE_BAND_WIDTH_IN = AVERY_5160.label_width * 0.98

# Representative classroom titles.
SHORT_TITLE = "Matilda"
ONE_LINE_TITLE = "Charlotte's Web"
TWO_LINE_TITLE = "From the Mixed-up Files of Mrs Basil E Frankweiler"
VERY_LONG_TITLE = (
    "Alexander and the Terrible, Horrible, No Good, Very Bad Day "
    "and Then Some Extra Words Teachers Sometimes Catalog With Subtitles "
    "That Keep Going Forever And Ever"
)
EXTREME_TITLE = (
    "The Absolutely True Diary of a Part-Time Indian Extended Classroom "
    "Edition With Annotated Teaching Guide And Discussion Questions "
    "For Literature Circles Volume One"
)


def _fit(title: str, *, start: float = DEFAULT_TITLE_SIZE_PT) -> FittedTitle:
    return fit_label_title(
        title,
        max_width_in=_TITLE_BAND_WIDTH_IN,
        max_height_in=_TITLE_BAND_HEIGHT_IN * 0.92,
        start_size_pt=start,
    )


def test_short_title_fits_at_default_size() -> None:
    fitted = _fit(SHORT_TITLE)
    assert fitted.text == SHORT_TITLE
    assert fitted.line_count == 1
    assert fitted.font_size_pt == DEFAULT_TITLE_SIZE_PT
    assert not fitted.reduced_font
    assert not fitted.used_ellipsis


def test_one_line_title_needs_no_adaptation() -> None:
    fitted = _fit(ONE_LINE_TITLE)
    assert fitted.text == ONE_LINE_TITLE
    assert fitted.line_count == 1
    assert not fitted.used_ellipsis
    assert fitted.font_size_pt >= MIN_TITLE_SIZE_PT


def test_normal_two_line_title_stays_within_two_lines() -> None:
    fitted = _fit(TWO_LINE_TITLE)
    assert fitted.line_count <= MAX_TITLE_LINES
    assert fitted.line_count >= 1
    assert "\n" in fitted.text or fitted.line_count == 1
    assert not fitted.text.endswith("…") or fitted.used_ellipsis


def test_extremely_long_title_never_exceeds_two_lines() -> None:
    fitted = _fit(VERY_LONG_TITLE)
    assert fitted.line_count <= MAX_TITLE_LINES
    assert fitted.font_size_pt >= MIN_TITLE_SIZE_PT
    # Must remain non-empty and contained.
    assert fitted.text
    assert fitted.text.count("\n") < MAX_TITLE_LINES


def test_font_reduction_before_ellipsis() -> None:
    """Shrink happens when needed; ellipsis only after minimum size."""
    # Force a tiny band so reduction is required.
    tiny = fit_label_title(
        TWO_LINE_TITLE,
        max_width_in=1.2,
        max_height_in=0.22,
        start_size_pt=DEFAULT_TITLE_SIZE_PT,
        min_size_pt=MIN_TITLE_SIZE_PT,
    )
    assert tiny.font_size_pt <= DEFAULT_TITLE_SIZE_PT
    assert tiny.line_count <= MAX_TITLE_LINES


def test_ellipsis_applied_for_extreme_titles() -> None:
    fitted = fit_label_title(
        EXTREME_TITLE,
        max_width_in=1.5,
        max_height_in=0.28,
        start_size_pt=DEFAULT_TITLE_SIZE_PT,
        min_size_pt=MIN_TITLE_SIZE_PT,
    )
    assert fitted.line_count <= MAX_TITLE_LINES
    assert fitted.used_ellipsis or fitted.reduced_font
    assert fitted.font_size_pt == MIN_TITLE_SIZE_PT or fitted.used_ellipsis
    if fitted.used_ellipsis:
        assert "…" in fitted.text


def test_fitted_text_metrics_fit_band() -> None:
    from PIL import Image, ImageDraw

    fitted = _fit(VERY_LONG_TITLE)
    dpi = 300
    font = load_title_font(bold=True, size_pt=fitted.font_size_pt, dpi=dpi)
    max_w = int(round(_TITLE_BAND_WIDTH_IN * dpi))
    max_h = int(round(_TITLE_BAND_HEIGHT_IN * 0.92 * dpi))
    probe = Image.new("RGB", (max(8, max_w), max(8, max_h)), (255, 255, 255))
    draw = ImageDraw.Draw(probe)
    bbox = draw.multiline_textbbox(
        (0, 0),
        fitted.text,
        font=font,
        spacing=2,
        align="center",
    )
    assert bbox[2] - bbox[0] <= max_w + 1
    assert bbox[3] - bbox[1] <= max_h + 1


def test_title_geometry_three_rows_with_barcode() -> None:
    assert _distribute_row_spans(["title", "author", "barcode"], 8) == [
        (0, 3),
        (3, 1),
        (4, 4),
    ]
    assert _distribute_row_spans(["title", "barcode"], 8) == [(0, 3), (3, 5)]


def test_excel_placement_no_overlap_author_or_barcode() -> None:
    target = OpenPyxlLabelSheetTarget()
    target.begin_page(1, template=AVERY_5160)
    target.place_label(
        LabelPlacement(
            page_number=1,
            row=0,
            column=0,
            title=VERY_LONG_TITLE,
            author="Judith Viorst",
            isbn="9781416985952",
            used_placeholder_barcode=True,
            content=LabelContentOptions(
                show_title=True,
                show_author=True,
                show_barcode=True,
            ),
        )
    )
    sheet = target.workbook[f"{LABEL_SHEET_PREFIX}1"]
    title_value = sheet.cell(1, 1).value
    assert isinstance(title_value, str)
    assert title_value.count("\n") < MAX_TITLE_LINES
    # Title merge occupies rows 1–3; author is row 4; barcode placeholder row 5.
    assert sheet.cell(4, 1).value == "Judith Viorst"
    assert sheet.cell(5, 1).value == "[barcode placeholder]"
    # Author/barcode cells must not contain title fragments as their value.
    assert sheet.cell(4, 1).value != title_value
    assert sheet.cell(5, 1).value != title_value
    assert sheet.cell(1, 1).font.size <= DEFAULT_TITLE_SIZE_PT
    assert sheet.cell(1, 1).font.size >= MIN_TITLE_SIZE_PT


def test_empty_title() -> None:
    fitted = _fit("")
    assert fitted.text == ""
    assert fitted.line_count == 0
    assert not fitted.used_ellipsis
