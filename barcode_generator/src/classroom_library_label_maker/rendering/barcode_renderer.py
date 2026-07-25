"""Barcode renderer backed by the ``python-barcode`` library.

Third-party types stay inside this module. Callers only see ``pathlib.Path``
and application enums from the :class:`BarcodeRenderer` contract.
"""

from __future__ import annotations

from pathlib import Path

from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.rendering.renderer import BarcodeSymbology

_logger = get_logger("rendering.python_barcode")


class PythonBarcodeRenderer:
    """Render barcode images using ``python-barcode`` and Pillow.

    Public methods accept and return only standard library / domain types so
    the service layer never imports vendor libraries.
    """

    def render_to_file(
        self,
        data: str,
        output_path: Path,
        *,
        symbology: BarcodeSymbology = BarcodeSymbology.EAN13,
    ) -> Path:
        """Render ``data`` as a barcode PNG at ``output_path``.

        Args:
            data: Payload to encode (normalized ISBN-13 digits for EAN-13).
            output_path: Destination image path (``.png`` expected).
            symbology: Target symbology. Only :attr:`BarcodeSymbology.EAN13`
                is supported in this release.

        Returns:
            ``output_path`` after a successful write.

        Raises:
            ValueError: If ``symbology`` is unsupported or ``data`` cannot be
                encoded as the requested symbology.
            OSError: If the image file cannot be written.
        """
        output_path = Path(output_path)
        _logger.debug(
            "Rendering barcode (data=%r, output_path=%s, symbology=%s)",
            data,
            output_path,
            symbology,
        )

        if symbology is not BarcodeSymbology.EAN13:
            raise ValueError(
                f"Unsupported symbology for PythonBarcodeRenderer: {symbology!s}"
            )

        try:
            from barcode import get_barcode_class
            from barcode.writer import ImageWriter
        except ImportError as exc:  # pragma: no cover - dependency is required
            raise ValueError(
                "python-barcode is required to render barcode images"
            ) from exc

        barcode_cls = get_barcode_class("ean13")
        try:
            barcode = barcode_cls(data, writer=ImageWriter())
        except Exception as exc:
            raise ValueError(f"Cannot encode EAN-13 barcode for data={data!r}") from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with output_path.open("wb") as handle:
                barcode.write(handle)
        except OSError:
            raise
        except Exception as exc:
            raise ValueError(
                f"Failed writing EAN-13 barcode image to {output_path}"
            ) from exc

        if not output_path.is_file() or output_path.stat().st_size <= 0:
            raise OSError(f"Barcode render produced an empty file: {output_path}")

        _logger.debug(
            "Rendered barcode to %s (%s bytes)", output_path, output_path.stat().st_size
        )
        return output_path
