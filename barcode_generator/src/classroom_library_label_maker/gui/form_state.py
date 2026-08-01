"""Immutable GUI form state and lightweight path validation.

Validation here is presentation-layer only (required fields present and
sensible). It does not import workbooks or generate barcodes.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from classroom_library_label_maker.models import LabelContentOptions


@dataclass(frozen=True, slots=True)
class GenerationFormState:
    """User selections collected by the main window."""

    inventory_workbook: Path | None = None
    barcode_folder: Path | None = None
    output_workbook: Path | None = None
    label_template_id: str | None = None
    label_content: LabelContentOptions = LabelContentOptions()
    lookup_missing_isbns: bool = True

    def with_inventory_workbook(self, path: Path | None) -> GenerationFormState:
        """Return a copy with ``inventory_workbook`` updated."""
        return replace(self, inventory_workbook=path)

    def with_barcode_folder(self, path: Path | None) -> GenerationFormState:
        """Return a copy with ``barcode_folder`` updated."""
        return replace(self, barcode_folder=path)

    def with_output_workbook(self, path: Path | None) -> GenerationFormState:
        """Return a copy with ``output_workbook`` updated."""
        return replace(self, output_workbook=path)

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

        if self.output_workbook is None:
            messages.append("Choose where to save the label workbook.")
        else:
            parent = self.output_workbook.parent
            if str(parent) not in ("", ".") and not parent.is_dir():
                messages.append("The save folder doesn't exist yet.")
            elif self.output_workbook.suffix.lower() not in {".xlsx", ".xlsm"}:
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
