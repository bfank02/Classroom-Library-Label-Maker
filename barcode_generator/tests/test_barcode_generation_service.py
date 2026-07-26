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
    """Existing files should yield ALREADY_EXISTS without overwrite."""
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
    assert options["dpi"] == app_settings.barcode_dpi


def test_renderer_defaults_match_library_effective_output(tmp_path: Path) -> None:
    """Configured defaults must preserve prior python-barcode EAN-13 PNG output."""
    from barcode import get_barcode_class
    from barcode.writer import ImageWriter

    isbn = "9780064400558"
    baseline = tmp_path / "baseline.png"
    configured = tmp_path / "configured.png"

    barcode_cls = get_barcode_class("ean13")
    with baseline.open("wb") as handle:
        barcode_cls(isbn, writer=ImageWriter()).write(handle)

    PythonBarcodeRenderer().render_to_file(isbn, configured)

    assert configured.read_bytes() == baseline.read_bytes()
