"""Application configuration and project path resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from classroom_library_label_maker.constants import (
    APP_ICON_FILE_NAME,
    APP_ICNS_FILE_NAME,
    DEFAULT_BARCODE_DPI,
    DEFAULT_BARCODE_FONT_SIZE,
    DEFAULT_BARCODE_MODULE_HEIGHT,
    DEFAULT_BARCODE_MODULE_WIDTH,
    DEFAULT_BARCODE_QUIET_ZONE,
    DEFAULT_LABEL_TEMPLATE_ID,
    DEFAULT_LABEL_TYPE,
    DEFAULT_LOG_FILE_NAME,
    DEFAULT_LOG_LEVEL,
    DEFAULT_WORKBOOK_COLUMN_AUTHOR,
    DEFAULT_WORKBOOK_COLUMN_COPIES,
    DEFAULT_WORKBOOK_COLUMN_ISBN,
    DEFAULT_WORKBOOK_COLUMN_TITLE,
    DEFAULT_WORKBOOK_HEADER_ROW,
    DEFAULT_WORKBOOK_SHEET_NAME,
    DIR_ASSETS,
    DIR_BARCODES,
    DIR_ICONS,
    DIR_LOG_ARCHIVE,
    DIR_LOGS,
    DIR_OUTPUT,
    DIR_RESOURCES,
    DIR_SAMPLE_DATA,
    DIR_TEMP,
    DIR_TEMPLATES,
    LOGO_FILE_NAME,
    QUICK_START_FILE_NAME,
    SAMPLE_BOOKS_FILE_NAME,
    SAMPLE_INVENTORY_FILE_NAME,
    VERSION_FILE_NAME,
)
from classroom_library_label_maker.metadata import APP_VERSION
from classroom_library_label_maker.models import ApplicationSettings, LabelContentOptions
from classroom_library_label_maker.runtime_paths import (
    bundled_resource_root,
    is_frozen_application,
    user_data_directory,
    user_log_directory,
)


def find_project_root(start: Path | None = None) -> Path:
    """Locate the application resource root.

    In a frozen (PyInstaller) build, returns the bundled resource directory
    (``sys._MEIPASS``). During development, walks upward from ``start`` (or
    this file) until a directory containing both ``pyproject.toml`` and
    ``VERSION`` is found.

    Args:
        start: Optional starting path for the development-tree search.
            Ignored when the application is frozen.

    Returns:
        Absolute path to the resource root.

    Raises:
        FileNotFoundError: If no project root can be located in development.
    """
    if is_frozen_application():
        return bundled_resource_root()

    current = (start or Path(__file__)).resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file() and (
            candidate / VERSION_FILE_NAME
        ).is_file():
            return candidate

    raise FileNotFoundError(
        "Could not locate barcode_generator project root "
        f"(no {VERSION_FILE_NAME} + pyproject.toml found)."
    )


def read_version(project_root: Path | None = None) -> str:
    """Read the component version from the ``VERSION`` file.

    Prefers the on-disk ``VERSION`` file when the project tree is available.
    Falls back to :data:`~classroom_library_label_maker.metadata.APP_VERSION`
    when the file cannot be located (for example, a bare wheel install).

    Args:
        project_root: Optional project root; discovered automatically when omitted.

    Returns:
        Stripped version string (e.g. ``\"0.1.0\"``).
    """
    try:
        root = project_root or find_project_root()
        text = (root / VERSION_FILE_NAME).read_text(encoding="utf-8").strip()
    except (OSError, FileNotFoundError):
        return APP_VERSION
    return text or APP_VERSION


class ProjectPaths:
    """Resolved filesystem locations for assets and runtime directories.

    Bundled assets always resolve under the resource root (project tree or
    frozen ``_MEIPASS``). Writable runtime folders (logs, output, temp) use
    the project tree during development and per-user OS locations when frozen,
    because the bundle directory is not a reliable place for teacher-writable
    files.
    """

    def __init__(self, project_root: Path | None = None) -> None:
        """Initialize path helpers.

        Args:
            project_root: Optional explicit resource root. When provided,
                writable directories also resolve under this root (test-friendly
                and matches historical development behavior).
        """
        if project_root is not None:
            self.root = project_root.resolve()
            self._writable_root = self.root
            self._frozen = False
        elif is_frozen_application():
            self.root = find_project_root()
            self._writable_root = user_data_directory()
            self._frozen = True
        else:
            self.root = find_project_root()
            self._writable_root = self.root
            self._frozen = False

    @property
    def assets_dir(self) -> Path:
        """Return the assets directory."""
        return self.root / DIR_ASSETS

    @property
    def icons_dir(self) -> Path:
        """Return the icons directory."""
        return self.assets_dir / DIR_ICONS

    @property
    def templates_dir(self) -> Path:
        """Return the label templates directory."""
        return self.assets_dir / DIR_TEMPLATES

    @property
    def sample_data_dir(self) -> Path:
        """Return the sample-data directory."""
        return self.assets_dir / DIR_SAMPLE_DATA

    @property
    def resources_dir(self) -> Path:
        """Return the miscellaneous resources directory."""
        return self.assets_dir / DIR_RESOURCES

    @property
    def output_dir(self) -> Path:
        """Return the top-level output directory."""
        return self._writable_root / DIR_OUTPUT

    @property
    def barcodes_dir(self) -> Path:
        """Return the barcode PNG output directory."""
        return self.output_dir / DIR_BARCODES

    @property
    def logs_dir(self) -> Path:
        """Return the logs directory."""
        if self._frozen:
            return user_log_directory()
        return self._writable_root / DIR_LOGS

    @property
    def log_archive_dir(self) -> Path:
        """Return the rotated-log archive directory."""
        return self.logs_dir / DIR_LOG_ARCHIVE

    @property
    def temp_dir(self) -> Path:
        """Return the temporary scratch directory."""
        return self._writable_root / DIR_TEMP

    @property
    def version_file(self) -> Path:
        """Return the path to the ``VERSION`` file."""
        return self.root / VERSION_FILE_NAME

    @property
    def sample_books_file(self) -> Path:
        """Return the path to the sample books JSON file."""
        return self.sample_data_dir / SAMPLE_BOOKS_FILE_NAME

    @property
    def sample_inventory_file(self) -> Path:
        """Return the path to the bundled sample inventory workbook."""
        return self.sample_data_dir / SAMPLE_INVENTORY_FILE_NAME

    @property
    def app_icon_file(self) -> Path:
        """Return the path to the Windows ``.ico`` application icon."""
        return self.icons_dir / APP_ICON_FILE_NAME

    @property
    def app_icns_file(self) -> Path:
        """Return the path to the macOS ``.icns`` application icon."""
        return self.icons_dir / APP_ICNS_FILE_NAME

    @property
    def logo_file(self) -> Path:
        """Return the path to the logo image."""
        return self.icons_dir / LOGO_FILE_NAME

    @property
    def quick_start_file(self) -> Path:
        """Return the path to the bundled Quick Start guide."""
        return self.resources_dir / QUICK_START_FILE_NAME

    @property
    def default_log_file(self) -> Path:
        """Return the default application log file path."""
        return self.logs_dir / DEFAULT_LOG_FILE_NAME


def load_application_settings(
    *,
    project_root: Path | None = None,
    input_path: Path | str | None = None,
    results_path: Path | str | None = None,
    barcode_output_directory: Path | str | None = None,
    overwrite: bool = False,
    log_level: str = DEFAULT_LOG_LEVEL,
    log_file: Path | str | None = None,
    default_label_type: str = DEFAULT_LABEL_TYPE,
    label_template_id: str = DEFAULT_LABEL_TEMPLATE_ID,
    workbook_path: Path | str | None = None,
    workbook_sheet_name: str = DEFAULT_WORKBOOK_SHEET_NAME,
    label_content: LabelContentOptions | None = None,
) -> ApplicationSettings:
    """Build :class:`ApplicationSettings` from the project tree and overrides.

    Args:
        project_root: Optional project root override.
        input_path: Optional input JSON path for a run.
        results_path: Optional results JSON path for a run.
        barcode_output_directory: Optional barcode output directory override.
        overwrite: Whether to overwrite existing barcode images.
        log_level: Logging level name.
        log_file: Optional log file path override.
        default_label_type: Deprecated compatibility field; prefer setting
            ``label_template_id`` for layout.
        label_template_id: Registered template id for label layout (default
            ``avery-5160``).
        workbook_path: Optional Excel workbook path for import.
        workbook_sheet_name: Worksheet name used by Excel import.
        label_content: Optional label field visibility options.

    Returns:
        Populated :class:`ApplicationSettings`.

    Note:
        ``label_template_id`` is the template setting consumed by
        :class:`~classroom_library_label_maker.services.label_layout_service.LabelLayoutService`.
    """
    paths = ProjectPaths(project_root)
    version = read_version(paths.root)
    resolved_log_file = (
        Path(log_file) if log_file is not None else paths.default_log_file
    )
    return ApplicationSettings(
        barcode_output_directory=Path(barcode_output_directory)
        if barcode_output_directory is not None
        else paths.barcodes_dir,
        log_directory=paths.logs_dir,
        template_directory=paths.templates_dir,
        default_label_type=default_label_type,
        app_version=version,
        project_root=paths.root,
        input_path=Path(input_path) if input_path is not None else None,
        results_path=Path(results_path) if results_path is not None else None,
        overwrite=overwrite,
        log_level=log_level.upper(),
        log_file=resolved_log_file,
        barcode_module_width=DEFAULT_BARCODE_MODULE_WIDTH,
        barcode_module_height=DEFAULT_BARCODE_MODULE_HEIGHT,
        barcode_quiet_zone=DEFAULT_BARCODE_QUIET_ZONE,
        barcode_font_size=DEFAULT_BARCODE_FONT_SIZE,
        barcode_dpi=DEFAULT_BARCODE_DPI,
        workbook_path=Path(workbook_path) if workbook_path is not None else None,
        workbook_sheet_name=workbook_sheet_name,
        workbook_column_isbn=DEFAULT_WORKBOOK_COLUMN_ISBN,
        workbook_column_title=DEFAULT_WORKBOOK_COLUMN_TITLE,
        workbook_column_author=DEFAULT_WORKBOOK_COLUMN_AUTHOR,
        workbook_column_copies=DEFAULT_WORKBOOK_COLUMN_COPIES,
        workbook_header_row=DEFAULT_WORKBOOK_HEADER_ROW,
        label_template_id=label_template_id,
        label_content=label_content or LabelContentOptions(),
    )


@dataclass(slots=True)
class ExtensibilityHooks:
    """Feature flags for optional enrichment pipelines.

    These hooks keep the core batch pipeline extensible for ISBN lookup,
    cover downloads, inventory sync, and related future capabilities without
    requiring immediate implementations.

    Attributes:
        enable_isbn_lookup: When True, enrich book metadata via ISBN APIs.
        enable_cover_download: When True, download cover images for books.
        isbn_lookup_provider: Provider key for ISBN metadata (future use).
        cover_download_provider: Provider key for cover images (future use).
        extra: Free-form string settings for experimental providers.
    """

    enable_isbn_lookup: bool = False
    enable_cover_download: bool = False
    isbn_lookup_provider: str | None = None
    cover_download_provider: str | None = None
    # Provider credentials, timeouts, and cache directories will be added when
    # lookup/cover services are implemented.
    extra: dict[str, str] = field(default_factory=dict)
