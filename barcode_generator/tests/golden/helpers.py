"""Non-brittle helpers for golden barcode image comparisons.

Golden tests prefer structural and perceptual checks over byte-identical PNG
equality. See ``tests/golden/README.md`` for update guidance.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
import os
from pathlib import Path

from PIL import Image

GOLDEN_DIR = Path(__file__).resolve().parent
UPDATE_GOLDEN_ENV = "UPDATE_GOLDEN"

# Generous defaults: avoid flaky CI on minor antialias / font differences.
DEFAULT_MAX_DIMENSION_DELTA = 2
DEFAULT_MAX_HAMMING_DISTANCE = 8
AVERAGE_HASH_SIZE = 8


@dataclass(frozen=True, slots=True)
class ImageSimilarityResult:
    """Outcome of comparing an actual image to a golden reference."""

    similar: bool
    width_delta: int
    height_delta: int
    hamming_distance: int
    message: str


def golden_path_for(isbn: str, *, golden_dir: Path = GOLDEN_DIR) -> Path:
    """Return the expected golden PNG path for a normalized ISBN."""
    return Path(golden_dir) / f"{isbn}.png"


def iter_golden_images(*, golden_dir: Path = GOLDEN_DIR) -> Iterator[Path]:
    """Yield tracked golden PNG paths (excludes empty placeholders)."""
    yield from sorted(Path(golden_dir).glob("*.png"))


def should_update_goldens() -> bool:
    """Return True when ``UPDATE_GOLDEN`` requests reference refreshes."""
    value = os.environ.get(UPDATE_GOLDEN_ENV, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def average_hash(image: Image.Image, *, hash_size: int = AVERAGE_HASH_SIZE) -> int:
    """Compute a simple average hash for perceptual similarity.

    This is intentionally coarse so minor rendering noise does not fail tests.
    """
    gray = image.convert("L").resize(
        (hash_size, hash_size),
        Image.Resampling.LANCZOS,
    )
    pixels = list(gray.get_flattened_data())
    mean = sum(pixels) / len(pixels)
    bits = 0
    for index, value in enumerate(pixels):
        if value >= mean:
            bits |= 1 << index
    return bits


def hamming_distance(left: int, right: int) -> int:
    """Return the Hamming distance between two integer bitsets."""
    return (left ^ right).bit_count()


def compare_images(
    actual: Path,
    reference: Path,
    *,
    max_dimension_delta: int = DEFAULT_MAX_DIMENSION_DELTA,
    max_hamming_distance: int = DEFAULT_MAX_HAMMING_DISTANCE,
) -> ImageSimilarityResult:
    """Compare two PNGs using size tolerance and average-hash distance.

    Args:
        actual: Newly generated image.
        reference: Known-good golden image.
        max_dimension_delta: Allowed absolute width/height difference in pixels.
        max_hamming_distance: Allowed average-hash Hamming distance.

    Returns:
        Structured similarity result (never raises for visual mismatch).
    """
    actual_path = Path(actual)
    reference_path = Path(reference)

    if not actual_path.is_file():
        return ImageSimilarityResult(
            similar=False,
            width_delta=0,
            height_delta=0,
            hamming_distance=0,
            message=f"Actual image missing: {actual_path}",
        )
    if not reference_path.is_file():
        return ImageSimilarityResult(
            similar=False,
            width_delta=0,
            height_delta=0,
            hamming_distance=0,
            message=f"Golden reference missing: {reference_path}",
        )

    with (
        Image.open(actual_path) as actual_image,
        Image.open(reference_path) as ref_image,
    ):
        width_delta = abs(actual_image.width - ref_image.width)
        height_delta = abs(actual_image.height - ref_image.height)
        distance = hamming_distance(
            average_hash(actual_image),
            average_hash(ref_image),
        )

    size_ok = width_delta <= max_dimension_delta and height_delta <= max_dimension_delta
    hash_ok = distance <= max_hamming_distance
    similar = size_ok and hash_ok

    if similar:
        message = (
            f"Images similar (Δw={width_delta}, Δh={height_delta}, hamming={distance})"
        )
    else:
        message = (
            f"Images differ beyond tolerance (Δw={width_delta}, Δh={height_delta}, "
            f"hamming={distance}; limits Δ={max_dimension_delta}, "
            f"hamming≤{max_hamming_distance})"
        )

    return ImageSimilarityResult(
        similar=similar,
        width_delta=width_delta,
        height_delta=height_delta,
        hamming_distance=distance,
        message=message,
    )


def update_golden_from(actual: Path, reference: Path) -> Path:
    """Copy ``actual`` over ``reference`` after ensuring parent directories exist."""
    reference_path = Path(reference)
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    reference_path.write_bytes(Path(actual).read_bytes())
    return reference_path
