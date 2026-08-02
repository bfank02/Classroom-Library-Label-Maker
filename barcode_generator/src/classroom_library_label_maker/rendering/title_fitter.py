"""Font-metrics-based adaptive label title fitting.

Measures actual rendered width and height (via Pillow) to decide whether a
title fits in the allocated band, whether the font must shrink, and when an
ellipsis is required. Character-count heuristics are intentionally avoided.

Used by Excel and PDF label renderers so future templates share one strategy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Default Avery title styling (matches workbook_presentation.label_title_font).
DEFAULT_TITLE_SIZE_PT = 9.0
MIN_TITLE_SIZE_PT = 7.0
MAX_TITLE_LINES = 2
_FIT_DPI = 300
_LINE_SPACING_PX = 2
_ELLIPSIS = "…"


@dataclass(frozen=True, slots=True)
class FittedTitle:
    """Result of fitting a title into a label title band."""

    text: str
    """Display text (newline-separated; at most :data:`MAX_TITLE_LINES` lines)."""

    font_size_pt: float
    """Point size to apply when rendering."""

    line_count: int
    """Number of rendered lines (1 or 2, or 0 for empty)."""

    used_ellipsis: bool
    """True when the display text was truncated with an ellipsis."""

    reduced_font: bool
    """True when ``font_size_pt`` is below the requested start size."""


def fit_label_title(
    title: str,
    *,
    max_width_in: float,
    max_height_in: float,
    start_size_pt: float = DEFAULT_TITLE_SIZE_PT,
    min_size_pt: float = MIN_TITLE_SIZE_PT,
    max_lines: int = MAX_TITLE_LINES,
    bold: bool = True,
    dpi: int = _FIT_DPI,
    line_spacing_px: int = _LINE_SPACING_PX,
) -> FittedTitle:
    """Fit ``title`` into a rectangle using font metrics.

    Priority:

    1. Render at ``start_size_pt`` if the wrapped text fits in ``max_lines``
       and within the height.
    2. Reduce point size gradually down to ``min_size_pt``.
    3. At the minimum size, keep at most ``max_lines`` and ellipsize.

    Never returns text that overflows the allocated width/height band.
    """
    cleaned = " ".join(str(title or "").split())
    if not cleaned:
        return FittedTitle(
            text="",
            font_size_pt=start_size_pt,
            line_count=0,
            used_ellipsis=False,
            reduced_font=False,
        )

    max_width_px = max(1, int(round(max_width_in * dpi)))
    max_height_px = max(1, int(round(max_height_in * dpi)))
    max_lines = max(1, int(max_lines))
    start = float(start_size_pt)
    minimum = min(float(min_size_pt), start)

    sizes: list[float] = []
    size = start
    while size >= minimum - 1e-9:
        sizes.append(round(size, 2))
        if size <= minimum:
            break
        size = max(minimum, size - 1.0)

    from PIL import Image, ImageDraw

    probe = Image.new(
        "RGB",
        (max(8, max_width_px), max(8, max_height_px)),
        (255, 255, 255),
    )
    draw = ImageDraw.Draw(probe)

    for candidate in sizes:
        font = load_title_font(bold=bold, size_pt=candidate, dpi=dpi)
        wrapped = wrap_text_to_width(draw, cleaned, font, max_width_px)
        lines = [line for line in wrapped.split("\n") if line]
        at_minimum = candidate <= minimum + 1e-9

        if len(lines) > max_lines:
            if not at_minimum:
                continue
            display = _clamp_lines_with_ellipsis(
                draw,
                lines,
                font,
                max_width_px=max_width_px,
                max_lines=max_lines,
            )
            used_ellipsis = True
        else:
            display = "\n".join(lines)
            used_ellipsis = False

        if not _text_fits(
            draw,
            display,
            font,
            max_width_px=max_width_px,
            max_height_px=max_height_px,
            line_spacing_px=line_spacing_px,
        ):
            if not at_minimum:
                continue
            display = _shrink_until_fits(
                draw,
                display,
                font,
                max_width_px=max_width_px,
                max_height_px=max_height_px,
                line_spacing_px=line_spacing_px,
            )
            used_ellipsis = used_ellipsis or _ELLIPSIS in display

        line_count = display.count("\n") + 1 if display else 0
        return FittedTitle(
            text=display,
            font_size_pt=candidate,
            line_count=line_count,
            used_ellipsis=used_ellipsis,
            reduced_font=candidate < start - 1e-9,
        )

    # Should be unreachable; sizes always includes minimum.
    return FittedTitle(
        text=_ELLIPSIS,
        font_size_pt=minimum,
        line_count=1,
        used_ellipsis=True,
        reduced_font=True,
    )


def wrap_text_to_width(
    draw: object,
    text: str,
    font: object,
    max_width_px: int,
) -> str:
    """Word-wrap ``text`` so each line fits ``max_width_px`` (font metrics)."""
    words = text.split(" ")
    if not words:
        return ""

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if _line_width(draw, trial, font) <= max_width_px:
            current = trial
            continue
        lines.append(current)
        current = word
        while _line_width(draw, current, font) > max_width_px and len(current) > 1:
            split_at = max(1, len(current) // 2)
            for end in range(len(current) - 1, 0, -1):
                piece = current[:end] + "-"
                if _line_width(draw, piece, font) <= max_width_px:
                    split_at = end
                    break
            lines.append(current[:split_at] + "-")
            current = current[split_at:]
    lines.append(current)
    return "\n".join(lines)


def ellipsize_line(
    draw: object,
    text: str,
    font: object,
    max_width_px: int,
) -> str:
    """Truncate ``text`` with an ellipsis so it fits ``max_width_px``."""
    if not text:
        return ""
    if _line_width(draw, text, font) <= max_width_px:
        return text
    for end in range(len(text), 0, -1):
        candidate = text[:end].rstrip() + _ELLIPSIS
        if _line_width(draw, candidate, font) <= max_width_px:
            return candidate
    return _ELLIPSIS


def load_title_font(*, bold: bool, size_pt: float, dpi: int) -> object:
    """Load a TrueType font approximating Calibri/Arial for measurement."""
    from PIL import ImageFont

    size_px = max(6, int(round(size_pt * dpi / 72.0)))
    candidates: list[Path] = []
    try:
        import barcode as barcode_package

        font_dir = Path(barcode_package.__file__).resolve().parent / "fonts"
        candidates.append(
            font_dir / ("DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf")
        )
        candidates.append(font_dir / "DejaVuSansMono.ttf")
    except Exception:
        pass
    if bold:
        candidates.extend(
            [
                Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
                Path("/Library/Fonts/Arial Bold.ttf"),
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            ]
        )
    candidates.extend(
        [
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
            Path("/Library/Fonts/Arial.ttf"),
            Path("/System/Library/Fonts/Helvetica.ttc"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            try:
                return ImageFont.truetype(str(candidate), size=size_px)
            except OSError:
                continue
    return ImageFont.load_default()


def _line_width(draw: object, text: str, font: object) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)  # type: ignore[attr-defined]
    return int(bbox[2] - bbox[0])


def _text_fits(
    draw: object,
    text: str,
    font: object,
    *,
    max_width_px: int,
    max_height_px: int,
    line_spacing_px: int,
) -> bool:
    if not text:
        return True
    bbox = draw.multiline_textbbox(  # type: ignore[attr-defined]
        (0, 0),
        text,
        font=font,
        spacing=line_spacing_px,
        align="center",
    )
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    return width <= max_width_px and height <= max_height_px


def _clamp_lines_with_ellipsis(
    draw: object,
    lines: list[str],
    font: object,
    *,
    max_width_px: int,
    max_lines: int,
) -> str:
    if len(lines) <= max_lines:
        return "\n".join(lines)
    head = lines[: max_lines - 1]
    tail = " ".join(lines[max_lines - 1 :])
    return "\n".join([*head, ellipsize_line(draw, tail, font, max_width_px)])


def _shrink_until_fits(
    draw: object,
    display: str,
    font: object,
    *,
    max_width_px: int,
    max_height_px: int,
    line_spacing_px: int,
) -> str:
    lines = [line for line in display.split("\n") if line]
    while lines:
        trial = "\n".join(lines)
        if _text_fits(
            draw,
            trial,
            font,
            max_width_px=max_width_px,
            max_height_px=max_height_px,
            line_spacing_px=line_spacing_px,
        ):
            return trial
        if len(lines) == 1:
            return ellipsize_line(draw, lines[0], font, max_width_px)
        lines = lines[:-1]
        if lines:
            lines[-1] = ellipsize_line(draw, lines[-1], font, max_width_px)
    return _ELLIPSIS
