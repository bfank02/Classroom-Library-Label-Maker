"""Tests for frozen/packaged and platform path helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from classroom_library_label_maker.config import ProjectPaths, find_project_root
from classroom_library_label_maker.constants import DEFAULT_LOG_FILE_NAME
from classroom_library_label_maker.metadata import APP_NAME
from classroom_library_label_maker.runtime_paths import (
    bundled_resource_root,
    is_frozen_application,
    user_data_directory,
    user_log_directory,
)
from classroom_library_label_maker.user_paths import resolve_quick_start_guide


def test_is_frozen_false_in_development() -> None:
    assert is_frozen_application() is False


def test_bundled_resource_root_requires_frozen() -> None:
    with pytest.raises(RuntimeError, match="frozen"):
        bundled_resource_root()


def test_find_project_root_uses_development_tree() -> None:
    root = find_project_root()
    assert (root / "pyproject.toml").is_file()
    assert (root / "VERSION").is_file()
    assert (root / "assets").is_dir()


def test_user_log_directory_follows_platform_convention() -> None:
    log_dir = user_log_directory()
    assert APP_NAME in str(log_dir)
    if sys.platform == "darwin":
        assert log_dir == (Path.home() / "Library" / "Logs" / APP_NAME).resolve()
    elif sys.platform == "win32":
        assert log_dir.name == "logs"
        assert log_dir.parent.name == APP_NAME
    else:
        assert log_dir.name == "logs"


def test_user_data_directory_follows_platform_convention() -> None:
    data_dir = user_data_directory()
    assert data_dir.name == APP_NAME
    if sys.platform == "darwin":
        assert "Application Support" in data_dir.parts


def test_project_paths_dev_logs_under_project_root() -> None:
    paths = ProjectPaths()
    assert paths.logs_dir == paths.root / "logs"
    assert paths.default_log_file == paths.logs_dir / DEFAULT_LOG_FILE_NAME


def test_project_paths_frozen_uses_user_writable_logs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    meipass = tmp_path / "meipass"
    (meipass / "assets" / "sample-data").mkdir(parents=True)
    (meipass / "VERSION").write_text("0.1.0\n", encoding="utf-8")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)

    data_root = tmp_path / "userdata"
    log_root = tmp_path / "userlogs"
    monkeypatch.setattr(
        "classroom_library_label_maker.config.user_data_directory",
        lambda **_: data_root,
    )
    monkeypatch.setattr(
        "classroom_library_label_maker.config.user_log_directory",
        lambda **_: log_root,
    )

    paths = ProjectPaths()
    assert paths.root == meipass.resolve()
    assert paths.logs_dir == log_root
    assert paths.default_log_file == log_root / DEFAULT_LOG_FILE_NAME
    assert paths.temp_dir == data_root / "temp"
    assert paths.barcodes_dir == data_root / "output" / "barcodes"
    assert paths.sample_inventory_file == (
        meipass / "assets" / "sample-data" / "Sample Books.xlsx"
    )


def test_find_project_root_frozen_returns_meipass(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    meipass = tmp_path / "bundle"
    meipass.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    assert find_project_root() == meipass.resolve()


def test_resolve_quick_start_guide_from_docs() -> None:
    guide = resolve_quick_start_guide()
    assert guide is not None
    assert guide.name == "Quick Start.md"
    assert guide.is_file()
    assert "Classroom Library Label Maker" in guide.read_text(encoding="utf-8")
