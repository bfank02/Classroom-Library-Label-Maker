"""Application entry point for the barcode generator component.

Startup only: parse CLI arguments, initialize logging when needed, and
dispatch to a command handler. Business logic lives under ``services/``
(:class:`~classroom_library_label_maker.services.workbook_generation_service.WorkbookGenerationService`
for ``generate``).
"""

from __future__ import annotations

import sys

from classroom_library_label_maker.cli.commands import (
    EXIT_INTERNAL_ERROR,
    EXIT_INVALID_ARGUMENTS,
    EXIT_NOT_IMPLEMENTED,
    dispatch,
)
from classroom_library_label_maker.cli.parser import (
    COMMAND_GENERATE,
    COMMAND_VERSION,
    CliArgumentError,
    parse_args,
)
from classroom_library_label_maker.config import load_application_settings
from classroom_library_label_maker.exceptions import ApplicationError
from classroom_library_label_maker.logger import get_logger, setup_logging
from classroom_library_label_maker.metadata import APP_COMPONENT_NAME, APP_NAME


def main(argv: list[str] | None = None) -> int:
    """Start the barcode generator application.

    Args:
        argv: Optional argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (see ``cli.commands`` module docstring).
    """
    try:
        args = parse_args(argv)
    except CliArgumentError as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        return EXIT_INVALID_ARGUMENTS

    if args.command == COMMAND_VERSION:
        return dispatch(args, settings=None)

    if args.command == COMMAND_GENERATE:
        settings = load_application_settings(
            workbook_path=args.input,
            results_path=args.results,
            barcode_output_directory=args.output_dir,
            overwrite=args.overwrite,
            log_level=args.log_level,
            log_file=args.log_file,
        )
    else:
        settings = load_application_settings(
            log_level=args.log_level,
            log_file=args.log_file,
        )

    setup_logging(level=settings.log_level, log_file=settings.log_file)
    logger = get_logger()
    logger.info(
        "%s — %s v%s starting (%s)",
        APP_NAME,
        APP_COMPONENT_NAME,
        settings.app_version,
        args.command,
    )

    try:
        return dispatch(args, settings)
    except ApplicationError as exc:
        logger.error("%s", exc)
        if exc.__cause__ is not None:
            logger.debug("Caused by: %s", exc.__cause__, exc_info=exc.__cause__)
        return EXIT_INTERNAL_ERROR
    except NotImplementedError as exc:
        logger.error("Not implemented: %s", exc)
        return EXIT_NOT_IMPLEMENTED
    except Exception:
        logger.exception("Unhandled error during command execution")
        return EXIT_INTERNAL_ERROR


if __name__ == "__main__":
    sys.exit(main())
