"""Shared operational constants for the barcode generator package.

Product identity (name, version, license, authorship) lives in
:mod:`classroom_library_label_maker.metadata`. This module holds runtime
defaults and relative path segment names only.
"""

from __future__ import annotations

from classroom_library_label_maker.metadata import APP_PACKAGE_NAME

# Application / logging
APP_LOGGER_NAME = APP_PACKAGE_NAME
DEFAULT_LOG_FILE_NAME = "application.log"
DEFAULT_LOG_LEVEL = "INFO"

# Label templates
# Canonical setting / registry id (use ApplicationSettings.label_template_id).
DEFAULT_LABEL_TEMPLATE_ID = "avery-5160"
# Deprecated compatibility default for ApplicationSettings.default_label_type
# (legacy underscore form; not used by LabelLayoutService).
DEFAULT_LABEL_TYPE = "avery_5160"

# Barcode image files
DEFAULT_BARCODE_EXTENSION = ".png"

# EAN-13 PNG rendering defaults (python-barcode ImageWriter).
# Tuned for consumer laser printers on Avery 5160: thicker modules (≈SC6),
# integer-friendly width at 600 DPI, and a wide aspect so Title+Barcode
# placement can fill nearly the full label width without stretching.
DEFAULT_BARCODE_MODULE_WIDTH = 0.55  # mm (~13 px at 600 DPI; SC2 was 0.33)
DEFAULT_BARCODE_MODULE_HEIGHT = 14.0  # mm (bars); kept below prior 20 mm to widen aspect
DEFAULT_BARCODE_QUIET_ZONE = 6.05  # mm (= 11 modules; EAN-13 left quiet-zone minimum)
DEFAULT_BARCODE_FONT_SIZE = 7  # smaller human-readable digits → more room for bars
# python-barcode ImageWriter draws human-readable text with Pillow anchor "md"
# (bottom of glyphs at bars_end + text_distance). Values below ~pt2mm(font_size)
# overlap the bars.
DEFAULT_BARCODE_TEXT_DISTANCE = 4.0  # mm between bars and human-readable text
DEFAULT_BARCODE_DPI = 600

# Worksheet rows used to subdivide each physical label (title/author/barcode).
# Higher granularity lets Title+Barcode give nearly all height to the scan target.
LABEL_WORKSHEET_ROWS_PER_LABEL = 8

# Excel workbook import defaults
DEFAULT_WORKBOOK_SHEET_NAME = "Books"
DEFAULT_WORKBOOK_COLUMN_ISBN = "ISBN"
DEFAULT_WORKBOOK_COLUMN_TITLE = "Title"
DEFAULT_WORKBOOK_COLUMN_AUTHOR = "Author"
DEFAULT_WORKBOOK_COLUMN_COPIES = "Copies"
DEFAULT_WORKBOOK_HEADER_ROW = 1

# Rotating log file settings
LOG_MAX_BYTES = 1_048_576  # 1 MiB
LOG_BACKUP_COUNT = 5

# Resource directory names relative to the project root
DIR_ASSETS = "assets"
DIR_ICONS = "icons"
DIR_TEMPLATES = "templates"
DIR_SAMPLE_DATA = "sample-data"
DIR_RESOURCES = "resources"
DIR_OUTPUT = "output"
DIR_BARCODES = "barcodes"
DIR_LOGS = "logs"
DIR_LOG_ARCHIVE = "archive"
DIR_TEMP = "temp"

VERSION_FILE_NAME = "VERSION"
SAMPLE_BOOKS_FILE_NAME = "sample-books.json"
SAMPLE_INVENTORY_FILE_NAME = "Sample Books.xlsx"
APP_ICON_FILE_NAME = "app.ico"
APP_ICNS_FILE_NAME = "app.icns"
LOGO_FILE_NAME = "logo.png"
QUICK_START_FILE_NAME = "Quick Start.md"
