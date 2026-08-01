"""First-run and dialog path helpers for the desktop GUI.

Qt-free utilities shared by the GUI. Prefer last-used selections when still
valid, then Documents / sample inventory for first run.
"""

from __future__ import annotations

from pathlib import Path

from classroom_library_label_maker.config import ProjectPaths
from classroom_library_label_maker.constants import (
    DEFAULT_LABEL_FILENAME,
    QUICK_START_FILE_NAME,
    SAMPLE_INVENTORY_FILE_NAME,
)
from classroom_library_label_maker.gui_preferences import (
    usable_barcode_folder,
    usable_label_filename,
    usable_label_folder,
    usable_output_workbook,
)


def user_documents_directory() -> Path:
    """Return a sensible Documents folder for file dialogs.

    Prefers ``~/Documents`` when it exists; otherwise falls back to the home
    directory. Does not create folders.
    """
    documents = Path.home() / "Documents"
    if documents.is_dir():
        return documents.resolve()
    return Path.home().resolve()


def resolve_sample_inventory_workbook(
    *,
    project_root: Path | None = None,
) -> Path | None:
    """Return the sample inventory workbook path when a non-empty file exists.

    Search order:

    1. Bundled ``assets/sample-data/Sample Books.xlsx``
    2. Repo ``samples/Sample Books.xlsx`` (sibling of ``barcode_generator/``)
    """
    try:
        paths = ProjectPaths(project_root)
    except FileNotFoundError:
        return None

    candidates = [
        paths.sample_inventory_file,
        paths.root.parent / "samples" / SAMPLE_INVENTORY_FILE_NAME,
    ]
    for candidate in candidates:
        try:
            if candidate.is_file() and candidate.stat().st_size > 0:
                return candidate.resolve()
        except OSError:
            continue
    return None


def resolve_quick_start_guide(
    *,
    project_root: Path | None = None,
) -> Path | None:
    """Return the Quick Start guide path when a non-empty file exists.

    Search order:

    1. Bundled ``assets/resources/Quick Start.md`` (packaged releases)
    2. Repo ``docs/Quick Start.md`` (development checkout)
    """
    try:
        paths = ProjectPaths(project_root)
    except FileNotFoundError:
        return None

    candidates = [
        paths.quick_start_file,
        paths.root.parent / "docs" / QUICK_START_FILE_NAME,
    ]
    for candidate in candidates:
        try:
            if candidate.is_file() and candidate.stat().st_size > 0:
                return candidate.resolve()
        except OSError:
            continue
    return None


def inventory_dialog_start_directory(
    *,
    last_inventory_workbook: Path | None = None,
) -> str:
    """Starting folder for the inventory open dialog."""
    if last_inventory_workbook is not None:
        try:
            parent = last_inventory_workbook.parent
            if parent.is_dir():
                return str(parent.resolve())
        except OSError:
            pass
    sample = resolve_sample_inventory_workbook()
    if sample is not None:
        return str(sample.parent)
    return str(user_documents_directory())


def barcode_folder_dialog_start_directory(
    *,
    last_barcode_folder: Path | None = None,
) -> str:
    """Starting folder for the barcode folder dialog.

    Prefers a still-valid last-used barcode folder, then Documents.
    """
    remembered = usable_barcode_folder(last_barcode_folder)
    if remembered is not None:
        return str(remembered)
    return str(user_documents_directory())


def label_folder_dialog_start_directory(
    *,
    last_label_folder: Path | None = None,
    last_output_workbook: Path | None = None,
) -> str:
    """Starting folder for the label folder dialog.

    Prefers a still-valid last-used label folder, then the parent of a legacy
    full output path, then Documents.
    """
    remembered = usable_label_folder(last_label_folder)
    if remembered is not None:
        return str(remembered)
    legacy = usable_output_workbook(last_output_workbook)
    if legacy is not None:
        return str(legacy.parent)
    return str(user_documents_directory())


def default_label_filename(
    *,
    last_label_filename: str | None = None,
    last_output_workbook: Path | None = None,
) -> str:
    """Return the label filename to show / persist on first run or restore."""
    remembered = usable_label_filename(last_label_filename)
    if remembered is not None:
        return remembered
    legacy = usable_output_workbook(last_output_workbook)
    if legacy is not None:
        return legacy.name
    return DEFAULT_LABEL_FILENAME


def label_workbook_save_dialog_defaults(
    *,
    last_output_workbook: Path | None = None,
    last_label_folder: Path | None = None,
    last_label_filename: str | None = None,
) -> tuple[str, str]:
    """Return ``(directory, suggested_filename)`` for legacy save dialogs.

    Prefers remembered folder + filename, then Documents with
    ``library_labels.xlsx``.
    """
    directory = label_folder_dialog_start_directory(
        last_label_folder=last_label_folder,
        last_output_workbook=last_output_workbook,
    )
    name = default_label_filename(
        last_label_filename=last_label_filename,
        last_output_workbook=last_output_workbook,
    )
    return directory, name
