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
            _draw_clipped_label_text(
                page,  # type: ignore[arg-type]
                text=str(value),
                left=left,
                top=band_top,
                width=label_w,
                height=band_h,
                font=font,
                dpi=dpi,
                fill_ratio=_TITLE_FILL,
                prefer_bold=(kind == "title"),
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


def _draw_clipped_label_text(
    page: object,
    *,
    text: str,
    left: float,
    top: float,
    width: float,
    height: float,
    font: object,
    dpi: int,
    fill_ratio: float,
    prefer_bold: bool,
) -> None:
    """Draw wrapped, centered text that cannot spill into neighboring labels."""
    from PIL import Image, ImageDraw

    pad = max(0.0, (1.0 - fill_ratio) / 2.0)
    band_w = max(1, _inches_to_px(width * (1.0 - 2.0 * pad), dpi))
    band_h = max(1, _inches_to_px(height * (1.0 - 2.0 * pad), dpi))
    band = Image.new("RGB", (band_w, band_h), (255, 255, 255))
    band_draw = ImageDraw.Draw(band)

    fitted_font, wrapped = _fit_wrapped_text(
        band_draw,
        text=text,
        font=font,
        max_width=max(1, band_w - 4),
        max_height=max(1, band_h - 2),
        prefer_bold=prefer_bold,
        dpi=dpi,
    )
    band_draw.multiline_text(
        (band_w // 2, band_h // 2),
        wrapped,
        font=fitted_font,
        fill=(0, 0, 0),
        anchor="mm",
        align="center",
        spacing=2,
    )

    x = _inches_to_px(left + width * pad, dpi)
    y = _inches_to_px(top + height * pad, dpi)
    page.paste(band, (x, y))  # type: ignore[attr-defined]


def _fit_wrapped_text(
    draw: object,
    *,
    text: str,
    font: object,
    max_width: int,
    max_height: int,
    prefer_bold: bool,
    dpi: int,
) -> tuple[object, str]:
    """Wrap ``text`` to ``max_width`` and shrink the font until it fits height."""
    cleaned = " ".join(text.split())
    if not cleaned:
        return font, ""

    # Try the provided font first, then step down a few point sizes.
    base_size = max(8, int(getattr(font, "size", 18)))
    size_pt_guess = base_size * 72.0 / float(dpi)
    candidates_pt = [
        size_pt_guess,
        size_pt_guess - 1,
        size_pt_guess - 2,
        max(6.0, size_pt_guess - 3),
    ]

    chosen_font = font
    chosen_text = cleaned
    for size_pt in candidates_pt:
        trial_font = _load_font(bold=prefer_bold, size_pt=size_pt, dpi=dpi)
        wrapped = _wrap_text(draw, cleaned, trial_font, max_width)
        bbox = draw.multiline_textbbox(  # type: ignore[attr-defined]
            (0, 0),
            wrapped,
            font=trial_font,
            spacing=2,
            align="center",
        )
        text_h = bbox[3] - bbox[1]
        text_w = bbox[2] - bbox[0]
        chosen_font = trial_font
        chosen_text = wrapped
        if text_h <= max_height and text_w <= max_width:
            return trial_font, wrapped

    # Still too tall: keep as many lines as fit and ellipsize the last line.
    lines = chosen_text.split("\n")
    kept: list[str] = []
    for index, line in enumerate(lines):
        trial = "\n".join([*kept, line])
        bbox = draw.multiline_textbbox(  # type: ignore[attr-defined]
            (0, 0),
            trial,
            font=chosen_font,
            spacing=2,
            align="center",
        )
        if bbox[3] - bbox[1] <= max_height:
            kept.append(line)
            continue
        if not kept:
            kept.append(_ellipsize_line(draw, line, chosen_font, max_width))
        else:
            kept[-1] = _ellipsize_line(draw, kept[-1], chosen_font, max_width)
        break
    return chosen_font, "\n".join(kept) if kept else _ellipsize_line(
        draw, cleaned, chosen_font, max_width
    )


def _wrap_text(draw: object, text: str, font: object, max_width: int) -> str:
    """Word-wrap ``text`` so each line fits ``max_width`` pixels."""
    words = text.split(" ")
    if not words:
        return ""

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        bbox = draw.textbbox((0, 0), trial, font=font)  # type: ignore[attr-defined]
        if bbox[2] - bbox[0] <= max_width:
            current = trial
            continue
        lines.append(current)
        current = word
        # Hard-break an oversized single token.
        while True:
            bbox = draw.textbbox((0, 0), current, font=font)  # type: ignore[attr-defined]
            if bbox[2] - bbox[0] <= max_width or len(current) <= 1:
                break
            # Leave room for a hyphen when splitting long words.
            split_at = max(1, len(current) // 2)
            for end in range(len(current) - 1, 0, -1):
                piece = current[:end] + "-"
                piece_box = draw.textbbox((0, 0), piece, font=font)  # type: ignore[attr-defined]
                if piece_box[2] - piece_box[0] <= max_width:
                    split_at = end
                    break
            lines.append(current[:split_at] + "-")
            current = current[split_at:]
    lines.append(current)
    return "\n".join(lines)


def _ellipsize_line(draw: object, text: str, font: object, max_width: int) -> str:
    """Truncate ``text`` with an ellipsis so it fits ``max_width``."""
    if not text:
        return ""
    bbox = draw.textbbox((0, 0), text, font=font)  # type: ignore[attr-defined]
    if bbox[2] - bbox[0] <= max_width:
        return text
    ellipsis = "…"
    for end in range(len(text), 0, -1):
        candidate = text[:end].rstrip() + ellipsis
        box = draw.textbbox((0, 0), candidate, font=font)  # type: ignore[attr-defined]
        if box[2] - box[0] <= max_width:
            return candidate
    return ellipsis


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
