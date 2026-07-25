"""Immutable GUI form state and lightweight path validation.

Validation here is presentation-layer only (required fields present and
sensible). It does not import workbooks or generate barcodes.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GenerationFormState:
    """User selections collected by the main window."""

    inventory_workbook: Path | None = None
    barcode_folder: Path | None = None
    output_workbook: Path | None = None
    label_template_id: str | None = None

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

    def validation_messages(self) -> tuple[str, ...]:
        """Return user-friendly messages for each invalid required field."""
        messages: list[str] = []

        if self.inventory_workbook is None:
            messages.append("Select an inventory workbook.")
        elif not self.inventory_workbook.is_file():
            messages.append(
                f"Inventory workbook not found: {self.inventory_workbook}"
            )

        if self.barcode_folder is None:
            messages.append("Select a barcode folder.")
        elif not self.barcode_folder.is_dir():
            messages.append(f"Barcode folder not found: {self.barcode_folder}")

        if self.output_workbook is None:
            messages.append("Select an output workbook path.")
        else:
            parent = self.output_workbook.parent
            if str(parent) not in ("", ".") and not parent.is_dir():
                messages.append(
                    f"Output workbook folder does not exist: {parent}"
                )
            elif self.output_workbook.suffix.lower() not in {".xlsx", ".xlsm"}:
                messages.append(
                    "Output workbook must be an Excel file (.xlsx or .xlsm)."
                )

        if not self.label_template_id or not self.label_template_id.strip():
            messages.append("Select a label template.")

        return tuple(messages)

    @property
    def is_valid(self) -> bool:
        """True when all required fields pass lightweight validation."""
        return not self.validation_messages()
