"""Tests for production logging and runtime path helpers."""

from __future__ import annotations

from pathlib import Path

from classroom_library_label_maker.logger import (
    configured_log_file,
    setup_logging,
    user_facing_log_hint,
)
from classroom_library_label_maker.metadata import APP_NAME
from classroom_library_label_maker.runtime_env import (
    default_user_log_file,
    is_frozen,
    resource_root,
    user_app_data_directory,
)


def test_is_frozen_false_in_tests() -> None:
    assert is_frozen() is False


def test_resource_root_points_at_project() -> None:
    root = resource_root()
    assert (root / "assets").is_dir()
    assert (root / "pyproject.toml").is_file()


def test_user_app_data_includes_product_name() -> None:
    path = user_app_data_directory()
    assert APP_NAME in str(path)


def test_setup_logging_records_configured_file(tmp_path: Path) -> None:
    log_file = tmp_path / "nested" / "app.log"
    logger = setup_logging(level="INFO", log_file=log_file, console=False)
    logger.info("release-log-probe")
    assert configured_log_file() == log_file.resolve()
    assert log_file.is_file()
    assert "release-log-probe" in log_file.read_text(encoding="utf-8")
    assert str(log_file.resolve()) in user_facing_log_hint()


def test_default_user_log_file_under_app_data() -> None:
    path = default_user_log_file()
    assert path.name == "application.log"
    assert path.parent.name == "logs"
    assert APP_NAME in str(path)
