"""CLI command implementations and dispatch."""

from __future__ import annotations

import argparse
from collections.abc import Callable

from classroom_library_label_maker.cli.parser import (
    COMMAND_CLEAN,
    COMMAND_DIAGNOSTICS,
    COMMAND_GENERATE,
    COMMAND_VALIDATE,
    COMMAND_VERSION,
)
from classroom_library_label_maker.config import (
    load_application_settings,
    read_version,
)
from classroom_library_label_maker.exceptions import ApplicationError
from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.models import ApplicationSettings
from classroom_library_label_maker.services.batch_processor import BatchProcessor

CommandHandler = Callable[[argparse.Namespace, ApplicationSettings | None], int]

# Process exit codes used by the CLI.
EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_NOT_IMPLEMENTED = 2
EXIT_COMPLETED_WITH_ERRORS = 3


def dispatch(
    args: argparse.Namespace,
    settings: ApplicationSettings | None = None,
) -> int:
    """Dispatch a parsed CLI namespace to the matching command handler.

    Args:
        args: Parsed CLI arguments (must include ``command``).
        settings: Optional pre-loaded application settings.

    Returns:
        Process exit code.
    """
    command = getattr(args, "command", None)
    if command is None:
        raise ApplicationError("No CLI command specified.")

    handler = COMMAND_HANDLERS.get(command)
    if handler is None:
        raise ApplicationError(f"Unknown command: {command!r}")

    return handler(args, settings)


def run_generate(
    args: argparse.Namespace,
    settings: ApplicationSettings | None = None,
) -> int:
    """Run the barcode generation command.

    Args:
        args: Parsed generate-command arguments.
        settings: Optional settings; loaded from ``args`` when omitted.

    Returns:
        Process exit code.
    """
    resolved = settings or load_application_settings(
        input_path=args.input,
        results_path=args.results,
        barcode_output_directory=args.output_dir,
        overwrite=args.overwrite,
        log_level=args.log_level,
        log_file=args.log_file,
    )
    logger = get_logger()
    logger.info(
        "Running generate (v%s)",
        resolved.app_version,
    )

    try:
        processor = BatchProcessor(resolved)
        batch = processor.run()
    except NotImplementedError as exc:
        # Feature stubs still raise NotImplementedError until Sprint 1 work lands.
        logger.error("Not implemented: %s", exc)
        return EXIT_NOT_IMPLEMENTED

    if batch.error_count:
        logger.warning("Completed with %s error(s)", batch.error_count)
        return EXIT_COMPLETED_WITH_ERRORS

    logger.info("Completed successfully")
    return EXIT_SUCCESS


def run_version(
    args: argparse.Namespace,
    settings: ApplicationSettings | None = None,
) -> int:
    """Print the component version.

    Args:
        args: Parsed CLI arguments (unused beyond dispatch).
        settings: Optional settings; VERSION file is read when omitted.

    Returns:
        ``EXIT_SUCCESS``.
    """
    _ = args
    if settings is not None:
        print(settings.app_version)
    else:
        print(read_version())
    return EXIT_SUCCESS


def run_validate(
    args: argparse.Namespace,
    settings: ApplicationSettings | None = None,
) -> int:
    """Validate books JSON (reserved).

    Args:
        args: Parsed CLI arguments.
        settings: Optional application settings.

    Returns:
        ``EXIT_NOT_IMPLEMENTED``.
    """
    _ = (args, settings)
    raise NotImplementedError("validate command is not implemented yet")


def run_clean(
    args: argparse.Namespace,
    settings: ApplicationSettings | None = None,
) -> int:
    """Clean runtime artifacts (reserved).

    Args:
        args: Parsed CLI arguments.
        settings: Optional application settings.

    Returns:
        ``EXIT_NOT_IMPLEMENTED``.
    """
    _ = (args, settings)
    raise NotImplementedError("clean command is not implemented yet")


def run_diagnostics(
    args: argparse.Namespace,
    settings: ApplicationSettings | None = None,
) -> int:
    """Print diagnostics (reserved).

    Args:
        args: Parsed CLI arguments.
        settings: Optional application settings.

    Returns:
        ``EXIT_NOT_IMPLEMENTED``.
    """
    _ = (args, settings)
    raise NotImplementedError("diagnostics command is not implemented yet")


COMMAND_HANDLERS: dict[str, CommandHandler] = {
    COMMAND_GENERATE: run_generate,
    COMMAND_VERSION: run_version,
    COMMAND_VALIDATE: run_validate,
    COMMAND_CLEAN: run_clean,
    COMMAND_DIAGNOSTICS: run_diagnostics,
}
