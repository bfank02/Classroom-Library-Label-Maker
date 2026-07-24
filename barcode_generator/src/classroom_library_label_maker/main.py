"""Application entry point for the Classroom Library barcode generator.

This module contains only startup / CLI wiring. Business logic lives in
``services`` and supporting modules.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from classroom_library_label_maker.config import load_application_settings
from classroom_library_label_maker.constants import DEFAULT_LOG_LEVEL
from classroom_library_label_maker.logger import get_logger, setup_logging
from classroom_library_label_maker.services.batch_processor import BatchProcessor


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser.

    Returns:
        Configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(
        prog="barcode-generator",
        description=(
            "Generate EAN-13 barcode PNGs from a JSON file of classroom "
            "library books."
        ),
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=None,
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
        default=None,
        help="Path to write the JSON results file.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate barcode images even if they already exist.",
    )
    parser.add_argument(
        "--log-level",
        default=DEFAULT_LOG_LEVEL,
        help="Logging level (DEBUG, INFO, WARNING, ERROR).",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Optional path to write a rotating log file.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the component version and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Start the barcode generator application.

    Args:
        argv: Optional argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (``0`` on success, non-zero on failure).
    """
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    settings = load_application_settings(
        input_path=args.input,
        results_path=args.results,
        barcode_output_directory=args.output_dir,
        overwrite=args.overwrite,
        log_level=args.log_level,
        log_file=args.log_file,
    )

    if args.version:
        print(settings.app_version)
        return 0

    if args.input is None or args.results is None:
        parser.error("--input and --results are required unless --version is set")

    setup_logging(level=settings.log_level, log_file=settings.log_file)
    logger = get_logger()
    logger.info(
        "Classroom Library Barcode Generator v%s starting",
        settings.app_version,
    )

    try:
        processor = BatchProcessor(settings)
        batch = processor.run()
    except NotImplementedError as exc:
        logger.error("Not implemented: %s", exc)
        return 2
    except Exception:
        logger.exception("Unhandled error during barcode generation")
        return 1

    if batch.error_count:
        logger.warning("Completed with %s error(s)", batch.error_count)
        return 3

    logger.info("Completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
