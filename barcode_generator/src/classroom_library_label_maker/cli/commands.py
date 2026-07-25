"""CLI command implementations and dispatch.

The ``generate`` command is a thin adapter over
:class:`~classroom_library_label_maker.services.workbook_generation_service.WorkbookGenerationService`.
It must not validate ISBNs, generate barcodes, lay out labels, or recalculate
statistics already present on :class:`WorkbookGenerationResult`.

Exit codes
----------
* ``0`` — success
* ``1`` — invalid arguments
* ``2`` — input / import failure
* ``3`` — generation failure (barcodes, layout, or save)
* ``4`` — unexpected internal error
* ``5`` — reserved command not implemented
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

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
from classroom_library_label_maker.exceptions import (
    ApplicationError,
    BarcodeGenerationError,
    ConfigurationError,
    FileSystemError,
    InvalidWorkbookError,
    LabelLayoutError,
    WorkbookGenerationError,
)
from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.models import (
    ApplicationSettings,
    WorkbookGenerationResult,
)
from classroom_library_label_maker.services.workbook_generation_service import (
    WorkbookGenerationService,
)
from classroom_library_label_maker.utils.file_utils import ensure_directory, write_json

CommandHandler = Callable[[argparse.Namespace, ApplicationSettings | None], int]

# Process exit codes used by the CLI.
EXIT_SUCCESS = 0
EXIT_INVALID_ARGUMENTS = 1
EXIT_IMPORT_FAILURE = 2
EXIT_GENERATION_FAILURE = 3
EXIT_INTERNAL_ERROR = 4
EXIT_NOT_IMPLEMENTED = 5

# Backward-compatible aliases (prefer the named constants above).
EXIT_FAILURE = EXIT_INVALID_ARGUMENTS
EXIT_COMPLETED_WITH_ERRORS = EXIT_GENERATION_FAILURE


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
    """Run label workbook generation via :class:`WorkbookGenerationService`.

    Args:
        args: Parsed generate-command arguments.
        settings: Optional settings; loaded from ``args`` when omitted.

    Returns:
        Process exit code (see module docstring).
    """
    resolved = settings or load_application_settings(
        workbook_path=args.input,
        results_path=getattr(args, "results", None),
        barcode_output_directory=args.output_dir,
        overwrite=args.overwrite,
        log_level=args.log_level,
        log_file=args.log_file,
    )
    if resolved.workbook_path is None:
        resolved.workbook_path = Path(args.input)

    logger = get_logger()
    logger.info("Running generate via WorkbookGenerationService (v%s)", resolved.app_version)

    labels_output = getattr(args, "labels_output", None)
    results_path = getattr(args, "results", None)

    try:
        service = WorkbookGenerationService(resolved)
        result = service.generate(
            workbook_path=Path(args.input),
            output_path=Path(labels_output) if labels_output is not None else None,
        )
    except ConfigurationError as exc:
        logger.error("%s", exc)
        return EXIT_INVALID_ARGUMENTS
    except InvalidWorkbookError as exc:
        logger.error("%s", exc)
        return EXIT_IMPORT_FAILURE
    except FileSystemError as exc:
        logger.error("%s", exc)
        if "save" in exc.message.lower():
            return EXIT_GENERATION_FAILURE
        return EXIT_IMPORT_FAILURE
    except (
        LabelLayoutError,
        WorkbookGenerationError,
        BarcodeGenerationError,
    ) as exc:
        logger.error("%s", exc)
        return EXIT_GENERATION_FAILURE
    except ApplicationError as exc:
        logger.error("%s", exc)
        return EXIT_GENERATION_FAILURE

    if results_path is not None:
        _write_results_summary(Path(results_path), result)

    _print_generation_summary(result)
    logger.info("Completed successfully")
    return EXIT_SUCCESS


def _print_generation_summary(result: WorkbookGenerationResult) -> None:
    """Print a concise success summary from ``result`` (no recalculation)."""
    output = result.output_path
    print("Generation complete")
    print()
    print(f"Books imported: {result.books_imported}")
    print(f"Books processed: {result.books_processed}")
    print(f"Labels created: {result.labels_created}")
    print(f"Pages created: {result.pages_created}")
    print(f"Barcodes generated: {result.barcodes_generated}")
    print(f"Barcodes reused: {result.barcodes_reused}")
    print()
    print(f"Output workbook: {output}")
    print()
    print(f"Elapsed time: {result.elapsed_seconds:.3f}s")


def _write_results_summary(path: Path, result: WorkbookGenerationResult) -> None:
    """Persist ``result.to_dict()`` to ``path`` when ``--results`` is set."""
    ensure_directory(path.parent)
    write_json(path, result.to_dict())
    get_logger().info("Wrote results summary: %s", path)


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
        Never returns; raises ``NotImplementedError``.
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
        Never returns; raises ``NotImplementedError``.
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
        Never returns; raises ``NotImplementedError``.
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
