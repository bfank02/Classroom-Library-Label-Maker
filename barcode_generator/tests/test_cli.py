"""Tests for CLI parsing and command dispatch (WorkbookGenerationService path)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from classroom_library_label_maker.cli.commands import (
    EXIT_GENERATION_FAILURE,
    EXIT_IMPORT_FAILURE,
    EXIT_INVALID_ARGUMENTS,
    EXIT_NOT_IMPLEMENTED,
    EXIT_SUCCESS,
    dispatch,
    run_generate,
    run_version,
)
from classroom_library_label_maker.cli.parser import (
    COMMAND_GENERATE,
    COMMAND_VERSION,
    CliArgumentError,
    build_parser,
    parse_args,
)
from classroom_library_label_maker.config import load_application_settings
from classroom_library_label_maker.exceptions import (
    ApplicationError,
    FileSystemError,
    InvalidWorkbookError,
    WorkbookGenerationError,
)
from classroom_library_label_maker.main import main
from classroom_library_label_maker.models import WorkbookGenerationResult

WORKBOOKS = Path(__file__).resolve().parent / "assets" / "workbooks"
INVENTORY = WORKBOOKS / "integration_inventory.xlsx"
VALID_BOOKS = WORKBOOKS / "valid_books.xlsx"


def test_parse_args_defaults_to_generate() -> None:
    """Legacy flat flags should map to the generate command."""
    args = parse_args(
        ["--input", "books.xlsx", "--labels-output", "out.xlsx", "--overwrite"]
    )
    assert args.command == COMMAND_GENERATE
    assert args.input == Path("books.xlsx")
    assert args.labels_output == Path("out.xlsx")
    assert args.overwrite is True
    assert args.results is None


def test_parse_args_explicit_generate() -> None:
    """Explicit generate subcommand should parse the same options."""
    args = parse_args(
        [
            "generate",
            "-i",
            "books.xlsx",
            "-r",
            "results.json",
            "--log-level",
            "DEBUG",
        ]
    )
    assert args.command == COMMAND_GENERATE
    assert args.log_level == "DEBUG"
    assert args.results == Path("results.json")


def test_parse_args_missing_input_raises() -> None:
    """Missing --input should raise CliArgumentError."""
    with pytest.raises(CliArgumentError, match="required: --input"):
        parse_args(["generate"])


def test_parse_args_version_flag() -> None:
    """Legacy --version should dispatch as the version command."""
    args = parse_args(["--version"])
    assert args.command == COMMAND_VERSION


def test_parse_args_version_command() -> None:
    """version subcommand should be recognized."""
    args = parse_args(["version"])
    assert args.command == COMMAND_VERSION


def test_build_parser_lists_commands() -> None:
    """Parser help should mention generate and reserved commands."""
    help_text = build_parser().format_help()
    assert "generate" in help_text
    assert "validate" in help_text
    assert "diagnostics" in help_text
    assert "inventory Excel" in help_text or "label workbook" in help_text


def test_run_version_prints(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """version command should print the VERSION file contents."""
    (tmp_path / "VERSION").write_text("0.1.0\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    settings = load_application_settings(project_root=tmp_path)
    code = run_version(parse_args(["version"]), settings)
    captured = capsys.readouterr()
    assert code == EXIT_SUCCESS
    assert captured.out.strip() == "0.1.0"


def test_dispatch_unknown_command_raises() -> None:
    """Unknown commands should raise ApplicationError."""
    args = parse_args(["version"])
    args.command = "nope"
    with pytest.raises(ApplicationError, match="Unknown command"):
        dispatch(args)


def test_dispatch_validate_not_implemented() -> None:
    """Reserved validate command should surface NotImplementedError."""
    args = parse_args(["validate"])
    with pytest.raises(NotImplementedError):
        dispatch(args)


def test_main_version_exit_code() -> None:
    """main(--version) should return success without requiring input paths."""
    assert main(["--version"]) == EXIT_SUCCESS


def test_main_reserved_command_exit_code() -> None:
    """Reserved commands should return the not-implemented exit code."""
    assert main(["clean"]) == EXIT_NOT_IMPLEMENTED


def test_main_invalid_arguments_exit_code() -> None:
    """Missing required --input should return exit code 1."""
    assert main(["generate"]) == EXIT_INVALID_ARGUMENTS


def test_main_import_failure_exit_code(tmp_path: Path) -> None:
    """Missing inventory workbook should return exit code 2."""
    missing = tmp_path / "missing.xlsx"
    code = main(
        [
            "generate",
            "--input",
            str(missing),
            "--labels-output",
            str(tmp_path / "out.xlsx"),
            "--output-dir",
            str(tmp_path / "barcodes"),
            "--log-file",
            str(tmp_path / "app.log"),
        ]
    )
    assert code == EXIT_IMPORT_FAILURE


def test_run_generate_success_summary(
    app_settings,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Successful generate should print summary fields from the result."""
    result = WorkbookGenerationResult(
        books_imported=2,
        books_processed=2,
        labels_created=2,
        pages_created=1,
        barcodes_generated=2,
        barcodes_reused=0,
        output_path=tmp_path / "labels.xlsx",
        elapsed_seconds=1.25,
    )
    mock_service = MagicMock()
    mock_service.generate.return_value = result
    monkeypatch.setattr(
        "classroom_library_label_maker.cli.commands.WorkbookGenerationService",
        lambda settings: mock_service,
    )

    app_settings.workbook_path = VALID_BOOKS
    args = parse_args(
        [
            "generate",
            "-i",
            str(VALID_BOOKS),
            "-l",
            str(tmp_path / "labels.xlsx"),
        ]
    )
    code = run_generate(args, app_settings)
    captured = capsys.readouterr()

    assert code == EXIT_SUCCESS
    assert "Generation complete" in captured.out
    assert "Books imported: 2" in captured.out
    assert "Books processed: 2" in captured.out
    assert "Labels created: 2" in captured.out
    assert "Pages created: 1" in captured.out
    assert "Barcodes generated: 2" in captured.out
    assert "Barcodes reused: 0" in captured.out
    assert "Output workbook:" in captured.out
    assert "Elapsed time: 1.250s" in captured.out
    mock_service.generate.assert_called_once()


def test_run_generate_import_failure(
    app_settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """InvalidWorkbookError should map to exit code 2."""
    mock_service = MagicMock()
    mock_service.generate.side_effect = InvalidWorkbookError("bad sheet")
    monkeypatch.setattr(
        "classroom_library_label_maker.cli.commands.WorkbookGenerationService",
        lambda settings: mock_service,
    )
    args = parse_args(["generate", "-i", str(VALID_BOOKS)])
    assert run_generate(args, app_settings) == EXIT_IMPORT_FAILURE


def test_run_generate_generation_failure(
    app_settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WorkbookGenerationError should map to exit code 3."""
    mock_service = MagicMock()
    mock_service.generate.side_effect = WorkbookGenerationError("layout boom")
    monkeypatch.setattr(
        "classroom_library_label_maker.cli.commands.WorkbookGenerationService",
        lambda settings: mock_service,
    )
    args = parse_args(["generate", "-i", str(VALID_BOOKS)])
    assert run_generate(args, app_settings) == EXIT_GENERATION_FAILURE


def test_run_generate_save_failure(
    app_settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FileSystemError mentioning save should map to exit code 3."""
    mock_service = MagicMock()
    mock_service.generate.side_effect = FileSystemError(
        "Failed to save label workbook to x.xlsx: disk full"
    )
    monkeypatch.setattr(
        "classroom_library_label_maker.cli.commands.WorkbookGenerationService",
        lambda settings: mock_service,
    )
    args = parse_args(["generate", "-i", str(VALID_BOOKS)])
    assert run_generate(args, app_settings) == EXIT_GENERATION_FAILURE


def test_cli_integration_creates_workbook(tmp_path: Path) -> None:
    """main(generate) should create a label workbook via the real service."""
    assert INVENTORY.is_file()
    project = tmp_path / "proj"
    project.mkdir()
    (project / "VERSION").write_text("0.1.0\n", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        '[project]\nname="t"\nversion="0.1.0"\n',
        encoding="utf-8",
    )
    for relative in (
        "assets/templates",
        "output/barcodes",
        "logs/archive",
        "temp",
    ):
        (project / relative).mkdir(parents=True, exist_ok=True)

    # Run from a temp project by monkeypatching ProjectPaths discovery via
    # absolute output paths (service uses settings.project_root from load).
    labels_out = tmp_path / "labels.xlsx"
    barcodes = tmp_path / "barcodes"
    barcodes.mkdir()
    results = tmp_path / "results.json"
    log_file = tmp_path / "run.log"

    # load_application_settings needs a project root; pass via chdir
    import os

    previous = Path.cwd()
    try:
        os.chdir(project)
        code = main(
            [
                "generate",
                "--input",
                str(INVENTORY),
                "--labels-output",
                str(labels_out),
                "--output-dir",
                str(barcodes),
                "--results",
                str(results),
                "--log-file",
                str(log_file),
            ]
        )
    finally:
        os.chdir(previous)

    assert code == EXIT_SUCCESS
    assert labels_out.is_file()
    assert labels_out.stat().st_size > 0
    assert results.is_file()
    assert list(barcodes.glob("*.png"))
