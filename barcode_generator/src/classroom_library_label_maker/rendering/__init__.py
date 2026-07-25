"""Barcode rendering layer.

Isolates image encoding from business logic (validation, batch orchestration).
The public surface is library-agnostic so backends can be swapped without
changing the barcode generation service.

Public API
----------
* :class:`BarcodeRenderer` — rendering protocol
* :class:`BarcodeSymbology` — symbology identifiers
* :class:`PythonBarcodeRenderer` — python-barcode EAN-13 PNG backend
"""

from __future__ import annotations

from classroom_library_label_maker.rendering.barcode_renderer import (
    PythonBarcodeRenderer,
)
from classroom_library_label_maker.rendering.renderer import (
    BarcodeRenderer,
    BarcodeSymbology,
)

__all__ = [
    "BarcodeRenderer",
    "BarcodeSymbology",
    "PythonBarcodeRenderer",
]
