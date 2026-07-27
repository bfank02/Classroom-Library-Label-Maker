"""Fan-out label placements to multiple :class:`LabelSheetTarget` adapters."""

from __future__ import annotations

from classroom_library_label_maker.label_templates.label_template import LabelTemplate
from classroom_library_label_maker.workbooks.label_sheet_target import (
    LabelPlacement,
    LabelSheetTarget,
)


class TeeLabelSheetTarget:
    """Forward ``begin_page`` / ``place_label`` to every wrapped target."""

    def __init__(self, *targets: LabelSheetTarget) -> None:
        if not targets:
            raise ValueError("TeeLabelSheetTarget requires at least one target")
        self._targets = targets

    def begin_page(self, page_number: int, *, template: LabelTemplate) -> None:
        for target in self._targets:
            target.begin_page(page_number, template=template)

    def place_label(self, placement: LabelPlacement) -> None:
        for target in self._targets:
            target.place_label(placement)
