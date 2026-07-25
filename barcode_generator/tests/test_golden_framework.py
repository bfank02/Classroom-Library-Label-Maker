"""Framework tests for golden barcode comparison helpers.

These tests validate the comparison machinery itself. Comparisons against
checked-in golden PNGs are optional and skip when no references exist.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

from classroom_library_label_maker.models import ApplicationSettings, Book
from classroom_library_label_maker.services.barcode_generation_service import (
    BarcodeGenerationService,
)
from golden.helpers import (
    GOLDEN_DIR,
    average_hash,
    compare_images,
    golden_path_for,
    hamming_distance,
    iter_golden_images,
    should_update_goldens,
    update_golden_from,
)


def _write_solid_png(path: Path, *, size: tuple[int, int], color: int) -> Path:
    image = Image.new("L", size, color=color)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")
    return path


def _write_pattern_png(
    path: Path,
    *,
    size: tuple[int, int],
    left_color: int,
    right_color: int,
) -> Path:
    width, height = size
    image = Image.new("L", size, color=left_color)
    for x in range(width // 2, width):
        for y in range(height):
            image.putpixel((x, y), right_color)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")
    return path


def test_average_hash_identical_for_same_image(tmp_path: Path) -> None:
    """Identical images should produce a zero Hamming distance."""
    left = _write_solid_png(tmp_path / "a.png", size=(64, 32), color=200)
    right = _write_solid_png(tmp_path / "b.png", size=(64, 32), color=200)

    with Image.open(left) as left_image, Image.open(right) as right_image:
        distance = hamming_distance(average_hash(left_image), average_hash(right_image))

    assert distance == 0


def test_compare_images_accepts_near_identical(tmp_path: Path) -> None:
    """Near-identical images within tolerance should be reported similar."""
    left = _write_solid_png(tmp_path / "a.png", size=(64, 32), color=180)
    right = _write_solid_png(tmp_path / "b.png", size=(65, 32), color=180)

    result = compare_images(left, right, max_dimension_delta=2, max_hamming_distance=8)
    assert result.similar
    assert result.width_delta <= 2


def test_compare_images_rejects_clearly_different(tmp_path: Path) -> None:
    """Clearly different images should fail the similarity check."""
    left = _write_pattern_png(
        tmp_path / "a.png",
        size=(64, 32),
        left_color=0,
        right_color=255,
    )
    right = _write_pattern_png(
        tmp_path / "b.png",
        size=(64, 32),
        left_color=255,
        right_color=0,
    )

    result = compare_images(left, right, max_dimension_delta=0, max_hamming_distance=0)
    assert not result.similar
    assert result.hamming_distance > 0


def test_update_golden_from_writes_reference(tmp_path: Path) -> None:
    """UPDATE_GOLDEN helper should copy bytes to the golden path."""
    actual = _write_solid_png(tmp_path / "actual.png", size=(16, 16), color=42)
    reference = tmp_path / "golden" / "9780064400558.png"

    written = update_golden_from(actual, reference)

    assert written == reference
    assert reference.read_bytes() == actual.read_bytes()


def test_golden_path_for_uses_isbn_stem() -> None:
    """Golden filenames should be ``{normalized_isbn}.png``."""
    assert golden_path_for("9780064400558").name == "9780064400558.png"


def test_should_update_goldens_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """UPDATE_GOLDEN environment flag should enable refresh mode."""
    monkeypatch.delenv("UPDATE_GOLDEN", raising=False)
    assert should_update_goldens() is False
    monkeypatch.setenv("UPDATE_GOLDEN", "1")
    assert should_update_goldens() is True


@pytest.mark.parametrize("isbn", ["9780064400558"])
def test_optional_golden_barcode_regression(
    isbn: str,
    app_settings: ApplicationSettings,
) -> None:
    """Compare a generated barcode to a golden PNG when one is checked in.

    Skips when no reference image exists. Set ``UPDATE_GOLDEN=1`` to write or
    refresh the golden from the current renderer output (review before commit).
    """
    reference = golden_path_for(isbn)
    service = BarcodeGenerationService(app_settings)
    book = Book(isbn=isbn, title="Golden sample", author="Test", copies=1)
    result = service.generate_for_book(book)
    assert result.output_path is not None
    actual = result.output_path

    if should_update_goldens():
        update_golden_from(actual, reference)
        pytest.skip(f"Updated golden reference at {reference}")

    if not reference.is_file():
        pytest.skip(f"No golden reference yet: {reference.name}")

    similarity = compare_images(actual, reference)
    assert similarity.similar, similarity.message


def test_iter_golden_images_only_pngs() -> None:
    """Iterator should only yield PNG files under the golden directory."""
    for path in iter_golden_images(golden_dir=GOLDEN_DIR):
        assert path.suffix.lower() == ".png"
        assert path.is_file()
