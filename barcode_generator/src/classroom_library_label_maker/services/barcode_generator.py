"""Deprecated legacy barcode path helpers (superseded by BarcodeGenerationService).

**Deprecated for new development.** Use
:class:`~classroom_library_label_maker.services.barcode_generation_service.BarcodeGenerationService`
with :class:`~classroom_library_label_maker.rendering.renderer.BarcodeRenderer`.

Retained for the CLI :class:`~classroom_library_label_maker.services.batch_processor.BatchProcessor`
compatibility path. ``generate()`` remains unimplemented.
"""

from __future__ import annotations

from pathlib import Path

from classroom_library_label_maker.constants import DEFAULT_BARCODE_EXTENSION
from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.utils.file_utils import ensure_directory, file_exists

_logger = get_logger("barcode_generator")


class BarcodeGenerator:
    """Deprecated: legacy path helpers for barcode PNGs.

    **Do not use for new features.** Prefer
    :class:`~classroom_library_label_maker.services.barcode_generation_service.BarcodeGenerationService`.

    Retained for CLI :class:`~classroom_library_label_maker.services.batch_processor.BatchProcessor`
    compatibility. ``generate()`` raises ``NotImplementedError``.
    """

    def __init__(self, *, default_extension: str = DEFAULT_BARCODE_EXTENSION) -> None:
        """Initialize the generator.

        Args:
            default_extension: File extension for barcode images (include dot).
        """
        self._default_extension = default_extension

    def output_path_for(self, isbn: str, output_dir: Path) -> Path:
        """Return the target PNG path for an ISBN.

        Args:
            isbn: Normalized ISBN digits.
            output_dir: Directory where images are stored.

        Returns:
            Full path to the barcode image file.
        """
        return output_dir / f"{isbn}{self._default_extension}"

    def exists(self, isbn: str, output_dir: Path) -> bool:
        """Return whether a barcode image already exists for ``isbn``.

        Args:
            isbn: Normalized ISBN digits.
            output_dir: Directory where images are stored.

        Returns:
            ``True`` if the target file exists.
        """
        return file_exists(self.output_path_for(isbn, output_dir))

    def generate(self, isbn: str, output_dir: Path) -> Path:
        """Create an EAN-13 barcode PNG for ``isbn``.

        Args:
            isbn: Normalized, validated ISBN digits.
            output_dir: Directory where the PNG will be written.

        Returns:
            Path to the written PNG file.

        Raises:
            OSError: If the file cannot be written.
            ValueError: If ``isbn`` cannot be encoded as EAN-13.
            NotImplementedError: Until PNG generation is implemented.
        """
        ensure_directory(output_dir)
        output_path = self.output_path_for(isbn, output_dir)
        _logger.info("Generating barcode: %s -> %s", isbn, output_path)

        # python-barcode (EAN13) + Pillow writer, human-readable text, module
        # width / quiet zone / DPI options are deferred to feature implementation.
        raise NotImplementedError("EAN-13 PNG generation is not implemented")

    def generate_if_missing(
        self,
        isbn: str,
        output_dir: Path,
        *,
        overwrite: bool = False,
    ) -> tuple[Path, bool]:
        """Generate a barcode unless it already exists (and overwrite is off).

        Args:
            isbn: Normalized, validated ISBN digits.
            output_dir: Directory where the PNG will be written.
            overwrite: When True, regenerate even if the file exists.

        Returns:
            A tuple of ``(path, created)`` where ``created`` is ``False``
            when an existing file was skipped.
        """
        output_path = self.output_path_for(isbn, output_dir)
        if not overwrite and file_exists(output_path):
            _logger.info("Skipping existing barcode: %s", output_path)
            return output_path, False

        created_path = self.generate(isbn, output_dir)
        return created_path, True
