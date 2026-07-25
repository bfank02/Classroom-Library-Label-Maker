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

# Label templates (Sprint 3+)
DEFAULT_LABEL_TYPE = "avery_5160"
DEFAULT_LABEL_TEMPLATE_ID = "avery-5160"

# Barcode image files
DEFAULT_BARCODE_EXTENSION = ".png"

# EAN-13 PNG rendering defaults (python-barcode ImageWriter / EAN SC2).
# These values match the library's effective defaults so centralizing them
# in ApplicationSettings does not change rendered output.
DEFAULT_BARCODE_MODULE_WIDTH = 0.33  # mm (EAN-13 SC2)
DEFAULT_BARCODE_MODULE_HEIGHT = 15.0  # mm
DEFAULT_BARCODE_QUIET_ZONE = 6.5  # mm
DEFAULT_BARCODE_FONT_SIZE = 10
DEFAULT_BARCODE_DPI = 300

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
APP_ICON_FILE_NAME = "app.ico"
LOGO_FILE_NAME = "logo.png"
