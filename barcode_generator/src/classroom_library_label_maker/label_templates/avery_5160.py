"""Avery 5160 address-label sheet specification (inches only).

Official layout: U.S. Letter, 30 labels (3x10), each 1" x 2-5/8".
This module contains layout data only - no worksheet, rendering, or printing.
"""

from __future__ import annotations

from classroom_library_label_maker.label_templates.label_template import (
    LabelTemplateSpec,
    PageOrientation,
    PageSize,
)

AVERY_5160_TEMPLATE_ID = "avery-5160"

# Canonical Avery 5160 physical specification (inches).
AVERY_5160 = LabelTemplateSpec(
    template_id=AVERY_5160_TEMPLATE_ID,
    template_name="Avery 5160 Address Labels",
    vendor="Avery",
    product_number="5160",
    description=(
        "U.S. Letter address labels, 1 in x 2-5/8 in, 30 labels per sheet "
        "(3 columns x 10 rows)."
    ),
    page_size=PageSize.LETTER,
    orientation=PageOrientation.PORTRAIT,
    page_width=8.5,
    page_height=11.0,
    rows=10,
    columns=3,
    label_width=2.625,
    label_height=1.0,
    top_margin=0.5,
    left_margin=0.1875,
    horizontal_gap=0.125,
    vertical_gap=0.0,
)


class Avery5160:
    """Avery 5160 template accessor - immutable layout data only.

    Prefer :data:`AVERY_5160` for the shared frozen specification instance.
    """

    template_id = AVERY_5160_TEMPLATE_ID

    @staticmethod
    def as_template() -> LabelTemplateSpec:
        """Return the immutable Avery 5160 :class:`LabelTemplateSpec`."""
        return AVERY_5160
