"""Application metadata — single source of truth for product identity.

All user-facing and packaging-oriented application strings belong here so
modules do not hardcode product name, version, license, or authorship.

Version management
------------------
``APP_VERSION`` is a static constant kept in sync with the project-root
``VERSION`` file and ``pyproject.toml``. Reading ``VERSION`` at import time
was avoided because:

* When the package is installed as a wheel, ``VERSION`` may not sit next to
  the importable package tree.
* Import-time filesystem discovery couples metadata to ``config`` path helpers
  and risks circular imports.

Runtime settings still prefer the on-disk ``VERSION`` file via
:func:`classroom_library_label_maker.config.read_version` when the project
tree is available; that helper falls back to ``APP_VERSION``.

When cutting a release, update these three places together:

1. ``barcode_generator/VERSION``
2. ``APP_VERSION`` in this module
3. ``pyproject.toml`` ``[project].version`` (and related packaging fields)
"""

from __future__ import annotations

# --- Product identity ---------------------------------------------------------

APP_NAME: str = "Classroom Library Label Maker"
"""Human-readable product name."""

APP_DESCRIPTION: str = (
    "Generate printable Avery barcode labels for classroom library books "
    "from an Excel inventory workbook."
)
"""Short product description (CLI help, packaging)."""

APP_AUTHOR: str = "Classroom Library Label Maker contributors"
"""Primary author / contributor attribution string."""

APP_COMPANY: str = "Classroom Library Label Maker"
"""Organization or company name for about boxes and installers."""

APP_COPYRIGHT: str = "Copyright (c) 2026 Classroom Library Label Maker contributors"
"""Copyright notice for about dialogs, logs, and documentation footers."""

APP_VERSION: str = "1.4.0"
"""Semantic version string. Keep synchronized with ``VERSION`` and pyproject."""

APP_WEBSITE: str = "https://github.com/bfank02/Classroom-Library-Label-Maker"
"""Product / repository website (placeholder until a dedicated site exists)."""

APP_LICENSE: str = "MIT"
"""SPDX-style license identifier."""

# --- Technical identifiers (derived from product packaging) -------------------

APP_PACKAGE_NAME: str = "classroom_library_label_maker"
"""Importable Python package name."""

APP_DISTRIBUTION_NAME: str = "classroom-library-barcode-generator"
"""PyPI / install distribution name (``importlib.metadata``)."""

APP_CLI_NAME: str = "barcode-generator"
"""Console script / argparse ``prog`` name."""

APP_GUI_SCRIPT_NAME: str = "label-maker-gui"
"""Console script name that launches the desktop GUI."""

APP_EXECUTABLE_NAME: str = "Classroom Library Label Maker"
"""Desktop executable / .app bundle display name for packaged releases."""

APP_BUNDLE_IDENTIFIER: str = "com.classroomlibrarylabelmaker.app"
"""macOS bundle identifier (``CFBundleIdentifier``)."""

APP_COMPONENT_NAME: str = "Barcode Generator"
"""Name of this component within the larger product."""