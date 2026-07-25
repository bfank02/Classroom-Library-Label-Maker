"""Tests for CLI parsing and command dispatch."""

from __future__ import annotations

from pathlib import Path

import pytest

from classroom_library_label_maker.cli.commands import (
    EXIT_NOT_IMPLEMENTED,
    EXIT_SUCCESS,
    dispatch,
    run_version,
)
from classroom_library_label_maker.cli.parser import (
    COMMAND_GENERATE,
    COMMAND_VERSION,
    build_parser,
    parse_args,
)
from classroom_library_label_maker.config import load_application_settings
from classroom_library_label_maker.exceptions import ApplicationError
from classroom_library_label_maker.main import main


def test_parse_args_defaults_to_generate() -> None:
    """Legacy flat flags should map to the generate command."""
    args = parse_args(
        ["--input", "books.json", "--results", "results.json", "--overwrite"]
    )
    assert args.command == COMMAND_GENERATE
    assert args.input == Path("books.json")
    assert args.results == Path("results.json")
    assert args.overwrite is True


def test_parse_args_explicit_generate() -> None:
    """Explicit generate subcommand should parse the same options."""
    args = parse_args(
        [
            "generate",
            "-i",
            "books.json",
            "-r",
            "results.json",
            "--log-level",
            "DEBUG",
        ]
    )
    assert args.command == COMMAND_GENERATE
    assert args.log_level == "DEBUG"


def test_parse_args_version_flag() -> None:
    """Legacy --version should dispatch as the version command."""
    args = parse_args(["--version"])
    assert args.command == COMMAND_VERSION


def test_parse_args_version_command() -> None:
    """version subcommand should be recognized."""
    args = parse_args(["version"])
    assert args.command == COMMAND_VERSION


def test_build_parser_lists_future_commands() -> None:
    """Parser help should mention reserved commands."""
    help_text = build_parser().format_help()
    assert "generate" in help_text
    assert "validate" in help_text
    assert "diagnostics" in help_text


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
