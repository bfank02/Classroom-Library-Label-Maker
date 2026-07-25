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

# Barcode image files
DEFAULT_BARCODE_EXTENSION = ".png"

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
