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
# Standard EAN-13 SC2 module width — narrower bars scan more reliably with
# typical classroom handheld scanners than the prior wide (≈SC6) setting.
DEFAULT_BARCODE_MODULE_WIDTH = 0.33  # mm (EAN-13 SC2; ~16 px at 1200 DPI)
DEFAULT_BARCODE_MODULE_HEIGHT = 20.0  # mm
DEFAULT_BARCODE_QUIET_ZONE = 4.0  # mm (above EAN minimum quiet zone at SC2)
DEFAULT_BARCODE_FONT_SIZE = 10
# python-barcode ImageWriter draws human-readable text with Pillow anchor "md"
# (bottom of glyphs at bars_end + text_distance). Values below ~pt2mm(font_size)
# overlap the bars. Library default is 5 mm.
DEFAULT_BARCODE_TEXT_DISTANCE = 5.0  # mm between bars and human-readable text
# High-DPI source PNGs for the print-ready PDF raster.
DEFAULT_BARCODE_DPI = 1200
# Worksheet / PDF page raster DPI used when composing print output.
EXCEL_BARCODE_PRINT_DPI = 600

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
GUI_PREFERENCES_FILE_NAME = "gui_preferences.json"
