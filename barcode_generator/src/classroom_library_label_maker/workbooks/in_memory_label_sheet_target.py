"""In-memory :class:`LabelSheetTarget` for tests and non-Excel consumers."""

from __future__ import annotations

from classroom_library_label_maker.label_templates.label_template import LabelTemplate
from classroom_library_label_maker.workbooks.label_sheet_target import (
    LabelPlacement,
    LabelSheetTarget,
)


class InMemoryLabelSheetTarget:
    """Record label placements without touching Excel or openpyxl.

    Useful for unit tests and for callers that only need layout coordinates.
    """

    def __init__(self) -> None:
        """Initialize an empty target."""
        self.pages: list[int] = []
        self.placements: list[LabelPlacement] = []
        self.templates_by_page: dict[int, LabelTemplate] = {}

    def begin_page(self, page_number: int, *, template: LabelTemplate) -> None:
        """Record that a new page was started."""
        if page_number < 1:
            raise ValueError("page_number must be >= 1")
        self.pages.append(page_number)
        self.templates_by_page[page_number] = template

    def place_label(self, placement: LabelPlacement) -> None:
        """Append ``placement`` to the recorded list."""
        if placement.page_number not in self.templates_by_page:
            raise RuntimeError(
                f"place_label called for page {placement.page_number} "
                "before begin_page"
            )
        self.placements.append(placement)
