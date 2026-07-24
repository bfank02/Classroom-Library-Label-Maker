"""Tests for filesystem helpers."""

from __future__ import annotations

from pathlib import Path

from classroom_library_label_maker.utils.file_utils import (
    ensure_directory,
    file_exists,
    read_json,
    write_json,
)


def test_ensure_directory_creates_parents(tmp_path: Path) -> None:
    """ensure_directory should create nested directories."""
    target = tmp_path / "a" / "b" / "c"
    result = ensure_directory(target)
    assert result == target
    assert target.is_dir()


def test_write_and_read_json_round_trip(tmp_path: Path) -> None:
    """write_json / read_json should round-trip a dictionary."""
    path = tmp_path / "nested" / "data.json"
    write_json(path, {"books": [{"title": "A"}]})
    data = read_json(path)
    assert data == {"books": [{"title": "A"}]}


def test_file_exists(tmp_path: Path) -> None:
    """file_exists should distinguish missing vs present files."""
    path = tmp_path / "x.txt"
    assert file_exists(path) is False
    path.write_text("ok", encoding="utf-8")
    assert file_exists(path) is True
