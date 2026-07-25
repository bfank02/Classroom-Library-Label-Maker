"""Generate application branding icons (PNG + multi-size ICO).

Run from ``barcode_generator/``::

    python assets/icons/_generate_app_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
PNG_PATH = ROOT / "logo.png"
ICO_PATH = ROOT / "app.ico"

# Calm classroom teal / navy — avoid generic purple AI branding.
BG = (18, 74, 92)  # deep teal
FG = (245, 248, 250)  # off-white
ACCENT = (232, 168, 56)  # warm amber stripe


def _draw_mark(size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    margin = max(1, size // 16)
    draw.rounded_rectangle(
        (margin, margin, size - margin - 1, size - margin - 1),
        radius=max(2, size // 6),
        fill=BG,
    )

    # Book spine accent
    spine_w = max(2, size // 10)
    draw.rectangle(
        (margin + size // 8, margin + size // 5, margin + size // 8 + spine_w, size - margin - size // 5),
        fill=ACCENT,
    )

    # Simple barcode bars
    bar_top = margin + size // 4
    bar_bottom = size - margin - size // 4
    x = margin + size // 3
    pattern = (2, 1, 3, 1, 2, 2, 1, 3, 1, 2, 1, 2)
    scale = max(1, size // 48)
    for width in pattern:
        w = width * scale
        draw.rectangle((x, bar_top, x + w - 1, bar_bottom), fill=FG)
        x += w + scale

    return image


def main() -> None:
    sizes = [16, 32, 48, 64, 128, 256]
    images = [_draw_mark(s) for s in sizes]
    master = images[-1]
    master.save(PNG_PATH, format="PNG")
    # Pillow embeds the requested sizes when saving from the largest image.
    master.save(ICO_PATH, format="ICO", sizes=[(s, s) for s in sizes])
    print(f"wrote {PNG_PATH} ({PNG_PATH.stat().st_size} bytes)")
    print(f"wrote {ICO_PATH} ({ICO_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
