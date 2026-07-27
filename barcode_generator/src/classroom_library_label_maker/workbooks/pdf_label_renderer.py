"""Print-ready Avery label PDFs at full print DPI (bypass Excel image resampling).

Excel Print / Save-as-PDF downsamples embedded PNGs, which softens EAN bars.
This renderer composites each letter page as a high-DPI raster and writes a
multipage PDF teachers can print directly for reliable scanning.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from classroom_library_label_maker.constants import (
    EXCEL_BARCODE_PRINT_DPI,
    LABEL_WORKSHEET_ROWS_PER_LABEL,
)
from classroom_library_label_maker.label_templates.label_template import LabelTemplate
from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.utils.file_utils import ensure_directory
from classroom_library_label_maker.workbooks.label_sheet_target import LabelPlacement
from classroom_library_label_maker.workbooks.openpyxl_label_sheet_target import (
    _distribute_row_spans,
)

_logger = get_logger("workbooks.pdf_label_renderer")

# Reuse the Excel print DPI constant as the PDF page raster DPI.
_PDF_DPI = EXCEL_BARCODE_PRINT_DPI
_TITLE_FILL = 0.98
_BARCODE_FILL = 0.98


def write_labels_pdf(
    placements: list[LabelPlacement],
    template: LabelTemplate,
    path: Path,
    *,
    dpi: int = _PDF_DPI,
) -> Path:
    """Render ``placements`` to a multipage letter PDF at ``dpi``.

    Args:
        placements: Labels produced by :class:`LabelLayoutService`.
        template: Physical sheet geometry (inches).
        path: Destination ``.pdf`` path.
        dpi: Page raster resolution (600 recommended for laser printers).

    Returns:
        Resolved path written.
    """
    from PIL import Image, ImageDraw, ImageFont

    if dpi <= 0:
        raise ValueError("dpi must be positive")
    if not placements:
        raise ValueError("placements must not be empty")

    by_page: dict[int, list[LabelPlacement]] = defaultdict(list)
    for placement in placements:
        by_page[placement.page_number].append(placement)

    pages: list[Image.Image] = []
    font_title = _load_font(bold=True, size_pt=9, dpi=dpi)
    font_body = _load_font(bold=False, size_pt=8, dpi=dpi)

    for page_number in sorted(by_page):
        page = Image.new(
            "RGB",
            (_inches_to_px(template.page_width, dpi), _inches_to_px(template.page_height, dpi)),
            color=(255, 255, 255),
        )
        draw = ImageDraw.Draw(page)
        for placement in by_page[page_number]:
            _draw_label(
                page,
                draw,
                placement,
                template=template,
                dpi=dpi,
                font_title=font_title,
                font_body=font_body,
            )
        pages.append(page)

    destination = Path(path)
    ensure_directory(destination.parent)
    first, rest = pages[0], pages[1:]
    first.save(
        destination,
        format="PDF",
        resolution=float(dpi),
        save_all=bool(rest),
        append_images=rest,
    )
    for page in pages:
        page.close()
    _logger.info("Wrote print-ready label PDF: %s (%s pages @ %s DPI)", destination, len(pages), dpi)
    return destination.resolve()


def _draw_label(
    page: object,
    draw: object,
    placement: LabelPlacement,
    *,
    template: LabelTemplate,
    dpi: int,
    font_title: object,
    font_body: object,
) -> None:
    from PIL import Image

    left = template.left_margin + placement.column * (
        template.label_width + template.horizontal_gap
    )
    top = template.top_margin + placement.row * (
        template.label_height + template.vertical_gap
    )
    label_w = template.label_width
    label_h = template.label_height

    content = placement.content
    slots: list[tuple[str, str | None]] = []
    if content.show_title:
        slots.append(("title", placement.title))
    if content.show_author:
        slots.append(("author", placement.author))
    if content.show_barcode:
        slots.append(("barcode", None))
    if not slots:
        return

    kinds: list[str] = [kind for kind, _ in slots]
    spans = _distribute_row_spans(kinds, LABEL_WORKSHEET_ROWS_PER_LABEL)  # type: ignore[arg-type]
    block = float(LABEL_WORKSHEET_ROWS_PER_LABEL)

    for (kind, value), (row_offset, row_span) in zip(slots, spans, strict=True):
        band_top = top + label_h * (row_offset / block)
        band_h = label_h * (row_span / block)
        if kind in {"title", "author"} and value:
            font = font_title if kind == "title" else font_body
            _draw_centered_text(
                draw,
                text=str(value),
                left=left,
                top=band_top,
                width=label_w,
                height=band_h,
                font=font,
                dpi=dpi,
                fill_ratio=_TITLE_FILL,
            )
        elif kind == "barcode":
            _paste_barcode(
                page,  # type: ignore[arg-type]
                placement=placement,
                left=left,
                top=band_top,
                width=label_w,
                height=band_h,
                dpi=dpi,
            )


def _paste_barcode(
    page: object,
    *,
    placement: LabelPlacement,
    left: float,
    top: float,
    width: float,
    height: float,
    dpi: int,
) -> None:
    from PIL import Image

    if (
        placement.barcode_image_path is None
        or placement.used_placeholder_barcode
        or not Path(placement.barcode_image_path).is_file()
    ):
        return

    with Image.open(placement.barcode_image_path) as source:
        barcode = source.convert("RGB")
        band_w = _inches_to_px(width, dpi)
        band_h = _inches_to_px(height, dpi)
        max_w = max(1, int(round(band_w * _BARCODE_FILL)))
        max_h = max(1, int(round(band_h * _BARCODE_FILL)))
        aspect = barcode.width / float(barcode.height)
        if max_w / max_h > aspect:
            target_h = max_h
            target_w = max(1, int(round(target_h * aspect)))
        else:
            target_w = max_w
            target_h = max(1, int(round(target_w / aspect)))
        resized = barcode.resize((target_w, target_h), resample=Image.Resampling.NEAREST)

    x = _inches_to_px(left, dpi) + max(0, (band_w - target_w) // 2)
    y = _inches_to_px(top, dpi) + max(0, (band_h - target_h) // 2)
    page.paste(resized, (x, y))  # type: ignore[attr-defined]


def _draw_centered_text(
    draw: object,
    *,
    text: str,
    left: float,
    top: float,
    width: float,
    height: float,
    font: object,
    dpi: int,
    fill_ratio: float,
) -> None:
    del fill_ratio  # reserved for future padding tweaks
    draw.multiline_text(  # type: ignore[attr-defined]
        (
            _inches_to_px(left + width / 2.0, dpi),
            _inches_to_px(top + height / 2.0, dpi),
        ),
        text,
        font=font,
        fill=(0, 0, 0),
        anchor="mm",
        align="center",
    )


def _load_font(*, bold: bool, size_pt: float, dpi: int) -> object:
    from PIL import ImageFont

    size_px = max(8, int(round(size_pt * dpi / 72.0)))
    candidates: list[Path] = []
    try:
        import barcode as barcode_package

        font_dir = Path(barcode_package.__file__).resolve().parent / "fonts"
        candidates.append(font_dir / "DejaVuSansMono-Bold.ttf" if bold else font_dir / "DejaVuSansMono.ttf")
        candidates.append(font_dir / "DejaVuSansMono.ttf")
    except Exception:
        pass
    # Common macOS fonts for title readability.
    if bold:
        candidates.extend(
            [
                Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
                Path("/Library/Fonts/Arial Bold.ttf"),
            ]
        )
    candidates.extend(
        [
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
            Path("/Library/Fonts/Arial.ttf"),
            Path("/System/Library/Fonts/Helvetica.ttc"),
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            try:
                return ImageFont.truetype(str(candidate), size=size_px)
            except OSError:
                continue
    return ImageFont.load_default()


def _inches_to_px(inches: float, dpi: int) -> int:
    return max(0, int(round(inches * dpi)))
