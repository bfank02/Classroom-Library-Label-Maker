"""Tests for EAN-13 barcode image generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from classroom_library_label_maker.services.barcode_generator import BarcodeGenerator


@pytest.fixture
def generator() -> BarcodeGenerator:
    """Return a fresh :class:`BarcodeGenerator`."""
    return BarcodeGenerator()


def test_output_path_for(generator: BarcodeGenerator, tmp_path: Path) -> None:
    """Output path should be ``{isbn}.png`` under the output directory."""
    path = generator.output_path_for("9780064400558", tmp_path)
    assert path == tmp_path / "9780064400558.png"


def test_exists_false_when_missing(
    generator: BarcodeGenerator,
    tmp_path: Path,
) -> None:
    """exists() should be False when the PNG is not present."""
    assert generator.exists("9780064400558", tmp_path) is False


def test_exists_true_when_present(
    generator: BarcodeGenerator,
    tmp_path: Path,
) -> None:
    """exists() should be True when the PNG file is present."""
    target = tmp_path / "9780064400558.png"
    target.write_bytes(b"")
    assert generator.exists("9780064400558", tmp_path) is True


def test_generate_if_missing_skips_existing(
    generator: BarcodeGenerator,
    tmp_path: Path,
) -> None:
    """Existing images should be skipped when overwrite is False."""
    target = tmp_path / "9780064400558.png"
    target.write_bytes(b"png")
    path, created = generator.generate_if_missing(
        "9780064400558",
        tmp_path,
        overwrite=False,
    )
    assert path == target
    assert created is False


@pytest.mark.xfail(reason="PNG generation not implemented yet", strict=True)
def test_generate_writes_png(generator: BarcodeGenerator, tmp_path: Path) -> None:
    """generate() should write a non-empty PNG once implemented."""
    path = generator.generate("9780064400558", tmp_path)
    assert path.is_file()
    assert path.stat().st_size > 0
