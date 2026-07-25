"""Library-agnostic barcode rendering contracts.

This module defines the public rendering abstraction used by the barcode
generation service. Implementations must not leak third-party library types
through this interface.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Protocol


class BarcodeSymbology(StrEnum):
    """Supported barcode symbologies for future renderer implementations.

    Only ``EAN13`` is planned for the initial barcode engine. Additional
    values document extension points and must not be assumed implemented.
    """

    EAN13 = "ean13"
    CODE128 = "code128"
    QR = "qr"


class BarcodeRenderer(Protocol):
    """Protocol for rendering barcode images without exposing library types.

    Implementations translate validated payload strings into image files on
    disk. Callers (the barcode generation service) depend only on this
    contract so rendering backends can be swapped (python-barcode, alternate
    libraries, SVG writers, etc.) without changing business logic.
    """

    def render_to_file(
        self,
        data: str,
        output_path: Path,
        *,
        symbology: BarcodeSymbology = BarcodeSymbology.EAN13,
    ) -> Path:
        """Render ``data`` as a barcode image at ``output_path``.

        Args:
            data: Payload to encode (for EAN-13, a normalized 13-digit ISBN).
            output_path: Destination path for the image file (e.g. ``.png``).
            symbology: Barcode symbology to render. Defaults to EAN-13.

        Returns:
            The path of the written image (typically ``output_path``).

        Raises:
            NotImplementedError: When the backend or symbology is not ready.
            OSError: When the file cannot be written (future implementations).
            ValueError: When ``data`` cannot be encoded for ``symbology``
                (future implementations).
        """
        ...
