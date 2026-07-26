"""Library-agnostic worksheet target for label layout.

Callers place labels through this protocol so layout services never depend on
openpyxl worksheet objects. Physical inches stay on :class:`LabelTemplate`;
targets convert to implementation-specific units.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from classroom_library_label_maker.label_templates.label_template import LabelTemplate
from classroom_library_label_maker.models import LabelContentOptions


@dataclass(frozen=True, slots=True)
class LabelPlacement:
    """Immutable description of one label to place on a sheet.

    Attributes:
        page_number: 1-based page index.
        row: 0-based row within the template grid.
        column: 0-based column within the template grid.
        title: Book title.
        author: Book author.
        isbn: Book ISBN (as provided; not re-validated).
        barcode_image_path: Path to a PNG when available.
        used_placeholder_barcode: True when no usable barcode image was supplied.
        content: Which fields should appear on this label.
    """

    page_number: int
    row: int
    column: int
    title: str
    author: str
    isbn: str
    barcode_image_path: Path | None = None
    used_placeholder_barcode: bool = False
    content: LabelContentOptions = field(default_factory=LabelContentOptions)


class LabelSheetTarget(Protocol):
    """Protocol for writing labels onto worksheet pages without vendor types."""

    def begin_page(self, page_number: int, *, template: LabelTemplate) -> None:
        """Prepare page ``page_number`` (1-based) for the given template."""
        ...

    def place_label(self, placement: LabelPlacement) -> None:
        """Place one label according to ``placement``."""
        ...
