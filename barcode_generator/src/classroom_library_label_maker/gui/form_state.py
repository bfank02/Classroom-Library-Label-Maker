"""Immutable GUI form state and lightweight path validation.

Validation here is presentation-layer only (required fields present and
sensible). It does not import workbooks or generate barcodes.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from classroom_library_label_maker.constants import DEFAULT_LABEL_FILENAME
from classroom_library_label_maker.models import LabelContentOptions

# Characters illegal in Windows filenames (also awkward on macOS/Linux).
_INVALID_FILENAME_CHARS = set('<>:"/\\|?*')


def build_label_output_path(
    label_folder: Path | None,
    label_filename: str,
) -> Path | None:
    """Join label folder + filename into a full workbook path.

    Returns ``None`` when the folder is missing or the filename is blank.
    Does not create directories or check that the folder exists.
    """
    if label_folder is None:
        return None
    name = label_filename.strip()
    if not name:
        return None
    return label_folder / name


def filename_has_invalid_characters(filename: str) -> bool:
    """Return True when ``filename`` contains characters unsafe for workbooks."""
    return any(ch in _INVALID_FILENAME_CHARS or ord(ch) < 32 for ch in filename)


@dataclass(frozen=True, slots=True)
class GenerationFormState:
    """User selections collected by the main window."""

    inventory_workbook: Path | None = None
    barcode_folder: Path | None = None
    label_folder: Path | None = None
    label_filename: str = DEFAULT_LABEL_FILENAME
    label_template_id: str | None = None
    label_content: LabelContentOptions = LabelContentOptions()
    lookup_missing_isbns: bool = True

    @property
    def output_workbook(self) -> Path | None:
        """Full label workbook path constructed from folder + filename."""
        return build_label_output_path(self.label_folder, self.label_filename)

    def with_inventory_workbook(self, path: Path | None) -> GenerationFormState:
        """Return a copy with ``inventory_workbook`` updated."""
        return replace(self, inventory_workbook=path)

    def with_barcode_folder(self, path: Path | None) -> GenerationFormState:
        """Return a copy with ``barcode_folder`` updated."""
        return replace(self, barcode_folder=path)

    def with_label_folder(self, path: Path | None) -> GenerationFormState:
        """Return a copy with ``label_folder`` updated (filename unchanged)."""
        return replace(self, label_folder=path)

    def with_label_filename(self, filename: str) -> GenerationFormState:
        """Return a copy with ``label_filename`` updated."""
        return replace(self, label_filename=filename)

    def with_output_workbook(self, path: Path | None) -> GenerationFormState:
        """Set folder and filename from a full path (tests / migration)."""
        if path is None:
            return replace(self, label_folder=None)
        return replace(self, label_folder=path.parent, label_filename=path.name)

    def with_label_template_id(self, template_id: str | None) -> GenerationFormState:
        """Return a copy with ``label_template_id`` updated."""
        return replace(self, label_template_id=template_id)

    def with_label_content(self, content: LabelContentOptions) -> GenerationFormState:
        """Return a copy with ``label_content`` updated."""
        return replace(self, label_content=content)

    def with_lookup_missing_isbns(self, enabled: bool) -> GenerationFormState:
        """Return a copy with ``lookup_missing_isbns`` updated."""
        return replace(self, lookup_missing_isbns=enabled)

    def validation_messages(self) -> tuple[str, ...]:
        """Return concise, actionable messages for each invalid required field."""
        messages: list[str] = []

        if self.inventory_workbook is None:
            messages.append("Choose an inventory workbook.")
        elif not self.inventory_workbook.is_file():
            messages.append("That inventory workbook could not be found.")

        if self.barcode_folder is None:
            messages.append("Choose a folder for barcode images.")
        elif not self.barcode_folder.is_dir():
            messages.append("That barcode folder could not be found.")

        if self.label_folder is None:
            messages.append("Choose a label folder.")
        elif not self.label_folder.is_dir():
            messages.append("That label folder could not be found.")

        name = self.label_filename.strip()
        if not name:
            messages.append("Enter a label file name.")
        elif filename_has_invalid_characters(name):
            messages.append("That label file name contains invalid characters.")
        elif Path(name).suffix.lower() not in {".xlsx", ".xlsm"}:
            messages.append(
                "Save the label workbook as an Excel file (.xlsx)."
            )

        if not self.label_template_id or not self.label_template_id.strip():
            messages.append("Choose a label template.")

        if not self.label_content.is_valid:
            messages.append("Choose at least one field to show on labels.")

        return tuple(messages)

    @property
    def is_valid(self) -> bool:
        """True when all required fields pass lightweight validation."""
        return not self.validation_messages()
