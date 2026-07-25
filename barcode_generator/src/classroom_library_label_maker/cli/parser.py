"""Command-line argument parsing for the barcode generator."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from classroom_library_label_maker.constants import DEFAULT_LOG_LEVEL
from classroom_library_label_maker.metadata import (
    APP_CLI_NAME,
    APP_DESCRIPTION,
    APP_NAME,
)

COMMAND_GENERATE = "generate"
COMMAND_VALIDATE = "validate"
COMMAND_CLEAN = "clean"
COMMAND_VERSION = "version"
COMMAND_DIAGNOSTICS = "diagnostics"

KNOWN_COMMANDS: frozenset[str] = frozenset(
    {
        COMMAND_GENERATE,
        COMMAND_VALIDATE,
        COMMAND_CLEAN,
        COMMAND_VERSION,
        COMMAND_DIAGNOSTICS,
    }
)


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level argument parser with subcommands.

    Returns:
        Configured :class:`argparse.ArgumentParser`.
    """
    shared = _shared_options_parser()

    parser = argparse.ArgumentParser(
        prog=APP_CLI_NAME,
        description=f"{APP_NAME}. {APP_DESCRIPTION}",
        parents=[shared],
    )
    # Legacy top-level --version for convenience; prefer the ``version`` command.
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the component version and exit (alias for 'version').",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
        description="Available commands (default: generate when omitted).",
        metavar="{generate,validate,clean,version,diagnostics}",
    )

    generate = subparsers.add_parser(
        COMMAND_GENERATE,
        parents=[shared],
        help="Generate barcode PNG images from a books JSON file.",
    )
    _add_generate_arguments(generate)

    subparsers.add_parser(
        COMMAND_VALIDATE,
        parents=[shared],
        help="Validate ISBNs in a books JSON file (reserved for future use).",
    )
    subparsers.add_parser(
        COMMAND_CLEAN,
        parents=[shared],
        help="Remove generated runtime artifacts (reserved for future use).",
    )
    subparsers.add_parser(
        COMMAND_VERSION,
        parents=[shared],
        help="Print the component version and exit.",
    )
    subparsers.add_parser(
        COMMAND_DIAGNOSTICS,
        parents=[shared],
        help="Print environment and path diagnostics (reserved for future use).",
    )

    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments, defaulting to the ``generate`` command.

    Preserves legacy invocations that omit an explicit subcommand
    (flat ``--input`` / ``--results`` flags map to ``generate``).

    Args:
        argv: Optional argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Parsed :class:`argparse.Namespace` including ``command``.
    """
    raw = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()

    if "--version" in raw and not _has_explicit_command(raw):
        filtered = [token for token in raw if token != "--version"]
        return parser.parse_args([COMMAND_VERSION, *filtered])

    if not _has_explicit_command(raw):
        raw = [COMMAND_GENERATE, *raw]

    return parser.parse_args(raw)


def _shared_options_parser() -> argparse.ArgumentParser:
    """Return a parent parser with options shared by all commands."""
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--log-level",
        default=DEFAULT_LOG_LEVEL,
        help="Logging level (DEBUG, INFO, WARNING, ERROR).",
    )
    parent.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Optional path to write a rotating log file.",
    )
    return parent


def _has_explicit_command(raw: list[str]) -> bool:
    """Return whether ``raw`` already begins with a known subcommand."""
    return bool(raw) and raw[0] in KNOWN_COMMANDS


def _add_generate_arguments(parser: argparse.ArgumentParser) -> None:
    """Attach generate-command options to ``parser``."""
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        required=True,
        help="Path to input JSON file containing books.",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=None,
        help=(
            "Directory for generated barcode PNG images "
            "(default: <project>/output/barcodes)."
        ),
    )
    parser.add_argument(
        "--results",
        "-r",
        type=Path,
        required=True,
        help="Path to write the JSON results file.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate barcode images even if they already exist.",
    )
