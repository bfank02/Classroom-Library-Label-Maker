"""Tests for the barcode generation engine."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from classroom_library_label_maker.exceptions import (
    BarcodeGenerationError,
    FileSystemError,
)
from classroom_library_label_maker.models import (
    ApplicationSettings,
    BarcodeStatus,
    Book,
)
from classroom_library_label_maker.rendering.barcode_renderer import (
    PythonBarcodeRenderer,
)
from classroom_library_label_maker.rendering.renderer import BarcodeSymbology
from classroom_library_label_maker.services.barcode_generation_service import (
    BarcodeGenerationService,
)


@pytest.fixture
def sample_book() -> Book:
    """Return a book with a known-valid ISBN-13."""
    return Book(
        isbn="978-0-06-440055-8",
        title="Charlotte's Web",
        author="E. B. White",
        copies=1,
    )


@pytest.fixture
def service(app_settings: ApplicationSettings) -> BarcodeGenerationService:
    """Return a service using the real python-barcode renderer."""
    return BarcodeGenerationService(app_settings)


def test_successful_barcode_generation(
    service: BarcodeGenerationService,
    sample_book: Book,
) -> None:
    """Generating a new barcode should return GENERATED and write a PNG."""
    result = service.generate_for_book(sample_book)

    assert result.status == BarcodeStatus.GENERATED
    assert result.isbn == "9780064400558"
    assert result.title == sample_book.title
    assert result.output_path is not None
    assert result.output_path.is_file()
    assert result.output_path.stat().st_size > 0
    assert result.output_path.name == "9780064400558.png"


def test_correct_filename_uses_normalized_isbn(
    service: BarcodeGenerationService,
    sample_book: Book,
    app_settings: ApplicationSettings,
) -> None:
    """Output filename must be ``{normalized_isbn}.png`` under settings path."""
    result = service.generate_for_book(sample_book)
    expected = Path(app_settings.barcode_output_directory) / "9780064400558.png"
    assert result.output_path == expected


def test_png_file_exists_and_not_empty(
    service: BarcodeGenerationService,
    sample_book: Book,
) -> None:
    """PNG output must exist and contain image bytes."""
    result = service.generate_for_book(sample_book)
    assert result.output_path is not None
    data = result.output_path.read_bytes()
    assert data.startswith(b"\x89PNG")
    assert len(data) > 100


def test_output_directory_creation(
    app_settings: ApplicationSettings,
    sample_book: Book,
) -> None:
    """Missing output directories should be created automatically."""
    nested = app_settings.barcode_output_directory / "nested" / "out"
    app_settings.barcode_output_directory = nested
    assert not nested.exists()

    service = BarcodeGenerationService(app_settings)
    result = service.generate_for_book(sample_book)

    assert nested.is_dir()
    assert result.status == BarcodeStatus.GENERATED
    assert result.output_path is not None
    assert result.output_path.parent == nested


def test_existing_barcode_detection(
    service: BarcodeGenerationService,
    sample_book: Book,
) -> None:
    """Existing files with a matching render key should yield ALREADY_EXISTS."""
    first = service.generate_for_book(sample_book)
    assert first.status == BarcodeStatus.GENERATED
    assert first.output_path is not None
    original_size = first.output_path.stat().st_size

    renderer = MagicMock()
    guarded = BarcodeGenerationService(
        service._settings,
        renderer=renderer,
    )
    second = guarded.generate_for_book(sample_book)

    assert second.status == BarcodeStatus.ALREADY_EXISTS
    assert second.output_path == first.output_path
    assert second.output_path.stat().st_size == original_size
    renderer.render_to_file.assert_not_called()


def test_stale_render_profile_regenerates_barcode(
    service: BarcodeGenerationService,
    sample_book: Book,
) -> None:
    """PNGs from an older render profile must not be reused silently."""
    from classroom_library_label_maker.services.barcode_generation_service import (
        render_key_path_for,
    )

    first = service.generate_for_book(sample_book)
    assert first.status == BarcodeStatus.GENERATED
    assert first.output_path is not None
    key_path = render_key_path_for(first.output_path)
    key_path.write_text("stale-profile\n", encoding="utf-8")
    stale_bytes = first.output_path.read_bytes()

    second = service.generate_for_book(sample_book)
    assert second.status == BarcodeStatus.GENERATED
    assert second.output_path is not None
    assert second.output_path.read_bytes().startswith(b"\x89PNG")
    assert key_path.read_text(encoding="utf-8").strip() != "stale-profile"
    # File was rewritten under the current profile (size may match, content stamped).
    assert key_path.read_text(encoding="utf-8").strip() == service._render_key
    assert second.output_path.stat().st_size > 0
    del stale_bytes


def test_missing_render_key_regenerates_barcode(
    service: BarcodeGenerationService,
    sample_book: Book,
) -> None:
    """Legacy PNGs without a sidecar must regenerate under the current profile."""
    from classroom_library_label_maker.services.barcode_generation_service import (
        render_key_path_for,
    )

    first = service.generate_for_book(sample_book)
    assert first.output_path is not None
    key_path = render_key_path_for(first.output_path)
    key_path.unlink()

    second = service.generate_for_book(sample_book)
    assert second.status == BarcodeStatus.GENERATED
    assert key_path.is_file()


def test_optimized_png_dimensions(tmp_path: Path) -> None:
    """Print-optimized geometry should produce a wide high-DPI EAN-13 PNG."""
    from PIL import Image

    from classroom_library_label_maker.constants import (
        DEFAULT_BARCODE_DPI,
        DEFAULT_BARCODE_MODULE_HEIGHT,
        DEFAULT_BARCODE_MODULE_WIDTH,
        DEFAULT_BARCODE_QUIET_ZONE,
    )

    output = tmp_path / "dims.png"
    PythonBarcodeRenderer().render_to_file("9780394839127", output)
    image = Image.open(output)
    width, height = image.size
    assert image.mode == "RGB"
    assert width > height
    # SC2 geometry at 1200 DPI is narrower than the prior wide (0.55 mm) build.
    assert width >= 1800
    assert height >= 1200
    assert DEFAULT_BARCODE_DPI == 1200
    assert DEFAULT_BARCODE_MODULE_WIDTH == 0.33
    assert DEFAULT_BARCODE_MODULE_HEIGHT == 20.0
    assert DEFAULT_BARCODE_QUIET_ZONE == 4.0


def test_empty_existing_barcode_is_regenerated(
    service: BarcodeGenerationService,
    sample_book: Book,
) -> None:
    """Zero-byte leftovers from a failed render should be regenerated."""
    path = service.output_path_for("9780064400558")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")

    result = service.generate_for_book(sample_book)

    assert result.status == BarcodeStatus.GENERATED
    assert result.output_path is not None
    assert result.output_path.stat().st_size > 0
    assert result.output_path.read_bytes().startswith(b"\x89PNG")


def test_renderer_interaction(
    app_settings: ApplicationSettings,
    sample_book: Book,
    tmp_path: Path,
) -> None:
    """Service should call the configured renderer with EAN-13 symbology."""
    target = app_settings.barcode_output_directory / "9780064400558.png"

    def _fake_render(
        data: str,
        output_path: Path,
        *,
        symbology: BarcodeSymbology = BarcodeSymbology.EAN13,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        assert data == "9780064400558"
        assert symbology is BarcodeSymbology.EAN13
        return output_path

    renderer = MagicMock()
    renderer.render_to_file.side_effect = _fake_render
    service = BarcodeGenerationService(app_settings, renderer=renderer)

    result = service.generate_for_book(sample_book)

    assert result.status == BarcodeStatus.GENERATED
    renderer.render_to_file.assert_called_once()
    assert result.output_path == target


def test_filesystem_failure_creating_directory(
    app_settings: ApplicationSettings,
    sample_book: Book,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Directory creation failures should raise FileSystemError."""
    service = BarcodeGenerationService(app_settings)

    def _boom(path: Path) -> Path:
        raise OSError("permission denied")

    monkeypatch.setattr(
        "classroom_library_label_maker.services.barcode_generation_service.ensure_directory",
        _boom,
    )

    with pytest.raises(FileSystemError, match="output directory"):
        service.generate_for_book(sample_book)


def test_filesystem_failure_during_render(
    app_settings: ApplicationSettings,
    sample_book: Book,
) -> None:
    """OSError from the renderer should be mapped to FileSystemError."""
    renderer = MagicMock()
    renderer.render_to_file.side_effect = OSError("disk full")
    service = BarcodeGenerationService(app_settings, renderer=renderer)

    with pytest.raises(FileSystemError, match="write barcode"):
        service.generate_for_book(sample_book)


def test_rendering_failure_mapped_to_barcode_generation_error(
    app_settings: ApplicationSettings,
    sample_book: Book,
) -> None:
    """Non-OSError renderer failures should raise BarcodeGenerationError."""
    renderer = MagicMock()
    renderer.render_to_file.side_effect = ValueError("bad payload")
    service = BarcodeGenerationService(app_settings, renderer=renderer)

    with pytest.raises(BarcodeGenerationError, match="render barcode"):
        service.generate_for_book(sample_book)


def test_python_barcode_renderer_rejects_unsupported_symbology(
    tmp_path: Path,
) -> None:
    """PythonBarcodeRenderer should reject non-EAN13 symbologies."""
    renderer = PythonBarcodeRenderer()
    with pytest.raises(ValueError, match="Unsupported symbology"):
        renderer.render_to_file(
            "9780064400558",
            tmp_path / "x.png",
            symbology=BarcodeSymbology.QR,
        )


def test_output_path_for_uses_settings(
    app_settings: ApplicationSettings,
) -> None:
    """output_path_for should join settings directory and ISBN filename."""
    service = BarcodeGenerationService(app_settings)
    path = service.output_path_for("9780064400558")
    assert path == app_settings.barcode_output_directory / "9780064400558.png"


def test_default_renderer_uses_application_settings(
    app_settings: ApplicationSettings,
) -> None:
    """Default PythonBarcodeRenderer should take geometry from ApplicationSettings."""
    service = BarcodeGenerationService(app_settings)
    renderer = service._renderer
    assert isinstance(renderer, PythonBarcodeRenderer)
    options = renderer._writer_options()
    assert options["module_width"] == app_settings.barcode_module_width
    assert options["module_height"] == app_settings.barcode_module_height
    assert options["quiet_zone"] == app_settings.barcode_quiet_zone
    assert options["font_size"] == app_settings.barcode_font_size
    assert options["text_distance"] == app_settings.barcode_text_distance
    assert options["dpi"] == app_settings.barcode_dpi


def test_renderer_defaults_are_applied_to_image_writer(tmp_path: Path) -> None:
    """Configured print defaults must be passed through to python-barcode."""
    from barcode import get_barcode_class
    from barcode.writer import ImageWriter
    from PIL import Image

    from classroom_library_label_maker.constants import (
        DEFAULT_BARCODE_DPI,
        DEFAULT_BARCODE_FONT_SIZE,
        DEFAULT_BARCODE_MODULE_HEIGHT,
        DEFAULT_BARCODE_MODULE_WIDTH,
        DEFAULT_BARCODE_QUIET_ZONE,
        DEFAULT_BARCODE_TEXT_DISTANCE,
    )

    isbn = "9780064400558"
    baseline = tmp_path / "baseline.png"
    configured = tmp_path / "configured.png"

    barcode_cls = get_barcode_class("ean13")
    options = {
        "module_width": DEFAULT_BARCODE_MODULE_WIDTH,
        "module_height": DEFAULT_BARCODE_MODULE_HEIGHT,
        "quiet_zone": DEFAULT_BARCODE_QUIET_ZONE,
        "font_size": DEFAULT_BARCODE_FONT_SIZE,
        "text_distance": DEFAULT_BARCODE_TEXT_DISTANCE,
        "dpi": DEFAULT_BARCODE_DPI,
    }
    with baseline.open("wb") as handle:
        barcode_cls(isbn, writer=ImageWriter()).write(handle, options=options)
    # Match the post-write DPI stamp applied by PythonBarcodeRenderer.
    with Image.open(baseline) as image:
        image.load()
        image.save(baseline, format="PNG", dpi=(DEFAULT_BARCODE_DPI, DEFAULT_BARCODE_DPI))

    PythonBarcodeRenderer().render_to_file(isbn, configured)

    assert configured.read_bytes() == baseline.read_bytes()
    assert configured.stat().st_size > 0
    with Image.open(configured) as image:
        dpi_info = image.info.get("dpi")
        assert dpi_info is not None
        assert abs(dpi_info[0] - DEFAULT_BARCODE_DPI) < 0.01
        assert abs(dpi_info[1] - DEFAULT_BARCODE_DPI) < 0.01


def test_human_readable_text_does_not_overlap_bars(tmp_path: Path) -> None:
    """ISBN digits must sit below the bars, not superimposed on them.

    python-barcode's ImageWriter anchors text at the bottom of the glyph box, so
    ``text_distance`` must exceed the font height in mm or bars and digits collide.
    """
    from PIL import Image

    from classroom_library_label_maker.constants import (
        DEFAULT_BARCODE_DPI,
        DEFAULT_BARCODE_MODULE_HEIGHT,
        DEFAULT_BARCODE_TEXT_DISTANCE,
    )

    output = tmp_path / "overlap-check.png"
    PythonBarcodeRenderer().render_to_file("9780394839127", output)
    image = Image.open(output).convert("RGB")
    width, height = image.size
    pixels = image.load()

    margin_top_mm = 1.0
    bar_end_px = int(
        (margin_top_mm + DEFAULT_BARCODE_MODULE_HEIGHT) * DEFAULT_BARCODE_DPI / 25.4
    )
    # Sample a band just below the bars; it must be nearly white (gap before digits).
    gap_start = min(height - 1, bar_end_px + 1)
    gap_end = min(height, gap_start + max(2, int(0.5 * DEFAULT_BARCODE_DPI / 25.4)))
    assert gap_end > gap_start
    black_in_gap = 0
    samples = 0
    for y in range(gap_start, gap_end):
        for x in range(width):
            samples += 1
            if pixels[x, y][0] < 40:
                black_in_gap += 1
    assert black_in_gap / samples < 0.01, (
        f"Expected quiet gap below bars; black density={black_in_gap / samples:.3f} "
        f"(text_distance={DEFAULT_BARCODE_TEXT_DISTANCE})"
    )
