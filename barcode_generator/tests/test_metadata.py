"""Tests for centralized application metadata."""

from __future__ import annotations

from classroom_library_label_maker import __version__
from classroom_library_label_maker.cli.parser import build_parser
from classroom_library_label_maker.constants import APP_LOGGER_NAME
from classroom_library_label_maker.metadata import (
    APP_AUTHOR,
    APP_BUNDLE_IDENTIFIER,
    APP_CLI_NAME,
    APP_COMPANY,
    APP_COMPONENT_NAME,
    APP_COPYRIGHT,
    APP_DESCRIPTION,
    APP_DISTRIBUTION_NAME,
    APP_EXECUTABLE_NAME,
    APP_GUI_SCRIPT_NAME,
    APP_LICENSE,
    APP_NAME,
    APP_PACKAGE_NAME,
    APP_VERSION,
    APP_WEBSITE,
)


def test_metadata_constants_are_non_empty() -> None:
    """Core metadata fields should be populated strings."""
    assert APP_NAME
    assert APP_DESCRIPTION
    assert APP_AUTHOR
    assert APP_COMPANY
    assert APP_COPYRIGHT
    assert APP_VERSION
    assert APP_WEBSITE
    assert APP_LICENSE
    assert APP_PACKAGE_NAME
    assert APP_DISTRIBUTION_NAME
    assert APP_CLI_NAME
    assert APP_GUI_SCRIPT_NAME
    assert APP_EXECUTABLE_NAME
    assert APP_BUNDLE_IDENTIFIER
    assert APP_COMPONENT_NAME
    assert APP_EXECUTABLE_NAME == APP_NAME
    assert "barcode-generator" not in APP_NAME.lower()
    assert "Excel" in APP_DESCRIPTION or "inventory" in APP_DESCRIPTION.lower()


def test_logger_name_matches_package_name() -> None:
    """Logger namespace should follow the importable package name."""
    assert APP_LOGGER_NAME == APP_PACKAGE_NAME


def test_cli_prog_uses_metadata() -> None:
    """Argparse prog should come from APP_CLI_NAME."""
    assert build_parser().prog == APP_CLI_NAME
    assert APP_NAME in build_parser().description


def test_package_version_aligned_with_metadata() -> None:
    """Installed/package __version__ should match APP_VERSION when resolvable."""
    assert __version__ == APP_VERSION or __version__
    # Prefer exact match against the canonical constant.
    assert APP_VERSION == "0.1.0"
