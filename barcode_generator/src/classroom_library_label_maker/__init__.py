"""Classroom Library Label Maker — barcode generator package.

This package validates ISBNs and generates EAN-13 barcode images for
classroom library inventory workflows.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__"]

try:
    __version__ = version("classroom-library-barcode-generator")
except PackageNotFoundError:
    # Editable / source-tree runs before the distribution metadata exists.
    __version__ = "0.1.0"
