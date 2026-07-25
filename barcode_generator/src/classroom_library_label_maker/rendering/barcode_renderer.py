"""Placeholder barcode renderer backed by python-barcode (future).

No third-party rendering is performed in this module yet. The class exists to
reserve the implementation slot for the Barcode Generation Engine sprint.
"""

from __future__ import annotations

from pathlib import Path

from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.rendering.renderer import BarcodeSymbology

_logger = get_logger("rendering.python_barcode")


class PythonBarcodeRenderer:
    """BarcodeRenderer implementation that will use the ``python-barcode`` library.

    This is an architectural placeholder. Methods raise
    :class:`NotImplementedError` until the barcode generation feature is built.

    The class intentionally exposes no ``python-barcode`` or Pillow types in its
    public signature so it can satisfy :class:`BarcodeRenderer` without leaking
    vendor APIs into the service layer.
    """

    def render_to_file(
        self,
        data: str,
        output_path: Path,
        *,
        symbology: BarcodeSymbology = BarcodeSymbology.EAN13,
    ) -> Path:
        """Render a barcode image to ``output_path`` (not implemented).

        Args:
            data: Payload to encode (e.g. normalized ISBN-13 digits).
            output_path: Destination image path.
            symbology: Target symbology (EAN-13 for the initial engine).

        Returns:
            Never returns; raises until implemented.

        Raises:
            NotImplementedError: Always, until rendering is implemented.
        """
        _logger.debug(
            "PythonBarcodeRenderer.render_to_file placeholder "
            "(data=%r, output_path=%s, symbology=%s)",
            data,
            output_path,
            symbology,
        )
        # Future: encode with python-barcode + Pillow writer; write PNG bytes
        # to output_path; return output_path. Keep all vendor types private.
        raise NotImplementedError(
            "PythonBarcodeRenderer.render_to_file is not implemented yet"
        )
