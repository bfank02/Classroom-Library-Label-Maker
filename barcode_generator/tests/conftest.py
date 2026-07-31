"""Shared pytest fixtures for the barcode generator tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from classroom_library_label_maker.config import load_application_settings
from classroom_library_label_maker.models import ApplicationSettings, Book


@pytest.fixture(autouse=True)
def isolate_gui_preferences(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Keep GUI path preferences out of the real user-data directory."""
    preferences_path = tmp_path / "gui_preferences.json"
    monkeypatch.setattr(
        "classroom_library_label_maker.gui_preferences.default_gui_preferences_path",
        lambda: preferences_path,
    )
    monkeypatch.setattr(
        "classroom_library_label_maker.gui.controller.default_gui_preferences_path",
        lambda: preferences_path,
    )
    return preferences_path


@pytest.fixture
def sample_book() -> Book:
    """Return a sample book with a well-known ISBN-13 shape."""
    return Book(
        isbn="9780064400558",
        title="Charlotte's Web",
        author="E. B. White",
        copies=1,
    )


@pytest.fixture
def app_settings(tmp_path: Path) -> ApplicationSettings:
    """Return :class:`ApplicationSettings` rooted in a temporary directory.

    Creates a minimal project-like layout (``VERSION`` + ``pyproject.toml``)
    so path helpers resolve consistently in unit tests.
    """
    (tmp_path / "VERSION").write_text("0.1.0\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "test"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    for relative in (
        "assets/templates",
        "assets/icons",
        "assets/sample-data",
        "output/barcodes",
        "logs/archive",
        "temp",
    ):
        (tmp_path / relative).mkdir(parents=True, exist_ok=True)

    return load_application_settings(
        project_root=tmp_path,
        input_path=tmp_path / "books.json",
        results_path=tmp_path / "results.json",
        overwrite=False,
        log_level="DEBUG",
        log_file=tmp_path / "logs" / "application.log",
    )
