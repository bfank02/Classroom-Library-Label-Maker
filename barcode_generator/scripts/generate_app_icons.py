#!/usr/bin/env python3
"""Generate application icon artwork (logo.png, app.ico, app.icns).

Run from ``barcode_generator/``:

    python scripts/generate_app_icons.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ICONS_DIR = ROOT / "assets" / "icons"
SIZES_ICO = (16, 32, 48, 64, 128, 256)
ICONSET_FILES: dict[int, tuple[str, ...]] = {
    16: ("icon_16x16.png",),
    32: ("diana.k@example.org", "icon_32x32.png"),
    64: ("ivan.p@example.net",),
    128: ("icon_128x128.png",),
    256: ("wendy.h@example.net", "icon_256x256.png"),
    512: ("wendy.h@example.net", "icon_512x512.png"),
    1024: ("walt.e@example.net",),
}


def _draw_icon(size: int) -> Image.Image:
    """Draw a simple book + barcode mark at the requested pixel size."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    margin = max(1, size // 16)
    draw.rounded_rectangle(
        (margin, margin, size - margin - 1, size - margin - 1),
        radius=max(2, size // 8),
        fill=(18, 92, 92, 255),
    )

    book_left = size * 0.18
    book_top = size * 0.22
    book_right = size * 0.58
    book_bottom = size * 0.80
    draw.rounded_rectangle(
        (book_left, book_top, book_right, book_bottom),
        radius=max(1, size // 28),
        fill=(245, 241, 232, 255),
    )
    spine = book_left + (book_right - book_left) * 0.12
    draw.line(
        (spine, book_top + size * 0.04, spine, book_bottom - size * 0.04),
        fill=(18, 92, 92, 220),
        width=max(1, size // 64),
    )

    bar_top = size * 0.28
    bar_bottom = size * 0.72
    bar_left = size * 0.62
    bar_right = size * 0.84
    widths = [1.0, 0.5, 1.2, 0.5, 0.8, 1.4, 0.5, 1.0, 0.6, 1.1, 0.5, 0.9]
    total = sum(widths)
    cursor = bar_left
    gap = (bar_right - bar_left) * 0.04
    usable = (bar_right - bar_left) - gap * (len(widths) - 1)
    for index, weight in enumerate(widths):
        width = usable * (weight / total)
        if index % 2 == 0:
            draw.rectangle(
                (cursor, bar_top, cursor + width, bar_bottom),
                fill=(245, 241, 232, 255),
            )
        cursor += width + gap

    y = size * 0.78
    draw.line(
        (bar_left, y, bar_right, y),
        fill=(245, 241, 232, 180),
        width=max(1, size // 64),
    )

    accent = max(1, size // 32)
    draw.arc(
        (
            margin + accent,
            margin + accent,
            size - margin - accent,
            size - margin - accent,
        ),
        start=200,
        end=250,
        fill=(12, 64, 64, 90),
        width=max(1, size // 48),
    )
    return image


def write_logo_and_ico() -> None:
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    logo = _draw_icon(512)
    logo_path = ICONS_DIR / "logo.png"
    logo.save(logo_path, format="PNG")

    ico_images = [_draw_icon(size) for size in SIZES_ICO]
    ico_path = ICONS_DIR / "app.ico"
    ico_images[-1].save(
        ico_path,
        format="ICO",
        sizes=[(image.width, image.height) for image in ico_images],
        append_images=ico_images[:-1],
    )
    print(f"Wrote {logo_path.relative_to(ROOT)}")
    print(f"Wrote {ico_path.relative_to(ROOT)}")


def write_icns() -> None:
    icns_path = ICONS_DIR / "app.icns"
    if sys.platform != "darwin":
        print("Skipping app.icns generation (iconutil is macOS-only).")
        return

    iconset = ICONS_DIR / "AppIcon.iconset"
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir(parents=True)

    try:
        for size, names in ICONSET_FILES.items():
            rendered = _draw_icon(size)
            for name in names:
                rendered.save(iconset / name, format="PNG")

        result = subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(icns_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"iconutil failed ({result.returncode}): "
                f"{result.stderr or result.stdout}"
            )
    finally:
        if iconset.exists():
            shutil.rmtree(iconset)

    print(f"Wrote {icns_path.relative_to(ROOT)}")


def main() -> int:
    write_logo_and_ico()
    write_icns()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
