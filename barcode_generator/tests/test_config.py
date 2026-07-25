"""Tests for application configuration and path helpers."""

from __future__ import annotations

from pathlib import Path

from classroom_library_label_maker.config import (
    ExtensibilityHooks,
    ProjectPaths,
    load_application_settings,
    read_version,
)
from classroom_library_label_maker.constants import (
    DEFAULT_BARCODE_DPI,
    DEFAULT_BARCODE_FONT_SIZE,
    DEFAULT_BARCODE_MODULE_HEIGHT,
    DEFAULT_BARCODE_MODULE_WIDTH,
    DEFAULT_BARCODE_QUIET_ZONE,
    DEFAULT_LABEL_TEMPLATE_ID,
    DEFAULT_LABEL_TYPE,
)


def test_load_application_settings_reads_version(tmp_path: Path) -> None:
    """Settings should load version and default runtime folders from the tree."""
    (tmp_path / "VERSION").write_text("0.1.0\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    for relative in (
        "assets/templates",
        "output/barcodes",
        "logs",
        "temp",
    ):
        (tmp_path / relative).mkdir(parents=True, exist_ok=True)

    settings = load_application_settings(project_root=tmp_path)

    assert settings.app_version == "0.1.0"
    assert settings.barcode_output_directory == tmp_path / "output" / "barcodes"
    assert settings.log_directory == tmp_path / "logs"
    assert settings.template_directory == tmp_path / "assets" / "templates"
    assert settings.default_label_type == DEFAULT_LABEL_TYPE
    assert settings.label_template_id == DEFAULT_LABEL_TEMPLATE_ID
    assert settings.log_file == tmp_path / "logs" / "application.log"
    assert settings.barcode_module_width == DEFAULT_BARCODE_MODULE_WIDTH
    assert settings.barcode_module_height == DEFAULT_BARCODE_MODULE_HEIGHT
    assert settings.barcode_quiet_zone == DEFAULT_BARCODE_QUIET_ZONE
    assert settings.barcode_font_size == DEFAULT_BARCODE_FONT_SIZE
    assert settings.barcode_dpi == DEFAULT_BARCODE_DPI


def test_project_paths_sample_books(tmp_path: Path) -> None:
    """ProjectPaths should locate sample-data without hardcoded absolutes."""
    (tmp_path / "VERSION").write_text("0.1.0\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    sample = tmp_path / "assets" / "sample-data" / "sample-books.json"
    sample.parent.mkdir(parents=True)
    sample.write_text("{}", encoding="utf-8")

    paths = ProjectPaths(tmp_path)
    assert paths.sample_books_file == sample
    assert read_version(tmp_path) == "0.1.0"


def test_extensibility_hooks_defaults() -> None:
    """Future feature hooks should default to disabled."""
    hooks = ExtensibilityHooks()
    assert hooks.enable_isbn_lookup is False
    assert hooks.enable_cover_download is False
