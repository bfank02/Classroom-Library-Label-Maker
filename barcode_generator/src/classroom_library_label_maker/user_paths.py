"""First-run path helpers for dialogs (no persistent settings).

Qt-free utilities shared by the desktop GUI. Prefer the user's Documents
folder and the bundled sample inventory when present.
"""

from __future__ import annotations

from pathlib import Path

from classroom_library_label_maker.config import ProjectPaths
from classroom_library_label_maker.constants import SAMPLE_INVENTORY_FILE_NAME


def user_documents_directory() -> Path:
    """Return a sensible Documents folder for file dialogs.

    Prefers ``~/Documents`` when it exists; otherwise falls back to the home
    directory. Does not create folders or remember prior selections.
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


def inventory_dialog_start_directory() -> str:
    """Starting folder for the inventory open dialog."""
    sample = resolve_sample_inventory_workbook()
    if sample is not None:
        return str(sample.parent)
    return str(user_documents_directory())


def barcode_folder_dialog_start_directory() -> str:
    """Starting folder for the barcode folder dialog."""
    return str(user_documents_directory())


def label_workbook_save_dialog_defaults() -> tuple[str, str]:
    """Return ``(directory, suggested_filename)`` for the label save dialog."""
    directory = user_documents_directory()
    return str(directory), "library_labels.xlsx"
