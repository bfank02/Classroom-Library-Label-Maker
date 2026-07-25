"""Immutable physical label-sheet specifications.

All measurements are in **inches**. Templates never include worksheet,
rendering, or printing logic — future layout engines convert inches to
implementation-specific units.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class PageSize(StrEnum):
    """Supported page sizes for label sheets."""

    LETTER = "letter"
    A4 = "a4"


class PageOrientation(StrEnum):
    """Page orientation for a label sheet."""

    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class LabelTemplate(Protocol):
    """Physical specification of a sheet of labels (inches only).

    Implementations must be immutable value objects. This protocol deliberately
    excludes Excel, rendering, and printing concepts so
    ``LabelLayoutService`` can depend on layout data alone.
    """

    @property
    def template_id(self) -> str:
        """Stable machine id (e.g. ``avery-5160``)."""
        ...

    @property
    def template_name(self) -> str:
        """Human-readable template name."""
        ...

    @property
    def vendor(self) -> str:
        """Vendor / brand name."""
        ...

    @property
    def product_number(self) -> str:
        """Vendor product number."""
        ...

    @property
    def description(self) -> str:
        """Short description of the label product."""
        ...

    @property
    def page_size(self) -> PageSize:
        """Named page size."""
        ...

    @property
    def orientation(self) -> PageOrientation:
        """Page orientation."""
        ...

    @property
    def page_width(self) -> float:
        """Page width in inches."""
        ...

    @property
    def page_height(self) -> float:
        """Page height in inches."""
        ...

    @property
    def rows(self) -> int:
        """Number of label rows on the sheet."""
        ...

    @property
    def columns(self) -> int:
        """Number of label columns on the sheet."""
        ...

    @property
    def label_width(self) -> float:
        """Single label width in inches."""
        ...

    @property
    def label_height(self) -> float:
        """Single label height in inches."""
        ...

    @property
    def top_margin(self) -> float:
        """Top margin in inches."""
        ...

    @property
    def left_margin(self) -> float:
        """Left margin in inches."""
        ...

    @property
    def horizontal_gap(self) -> float:
        """Horizontal gap between labels in inches."""
        ...

    @property
    def vertical_gap(self) -> float:
        """Vertical gap between labels in inches."""
        ...

    @property
    def labels_per_page(self) -> int:
        """Derived: ``rows * columns``."""
        ...

    @property
    def printable_width(self) -> float:
        """Derived width of the label grid in inches."""
        ...

    @property
    def printable_height(self) -> float:
        """Derived height of the label grid in inches."""
        ...


@dataclass(frozen=True, slots=True)
class LabelTemplateSpec:
    """Immutable label-sheet specification (all lengths in inches).

    Prefer constructing vendor templates as module-level constants of this type
    (or thin wrappers) so runtime code cannot mutate physical specs.
    """

    template_id: str
    template_name: str
    vendor: str
    product_number: str
    description: str
    page_size: PageSize
    orientation: PageOrientation
    page_width: float
    page_height: float
    rows: int
    columns: int
    label_width: float
    label_height: float
    top_margin: float
    left_margin: float
    horizontal_gap: float
    vertical_gap: float

    def __post_init__(self) -> None:
        """Validate structural invariants for a physical template."""
        if not self.template_id.strip():
            raise ValueError("template_id must not be empty")
        if self.rows < 1 or self.columns < 1:
            raise ValueError("rows and columns must be >= 1")
        for name in (
            "page_width",
            "page_height",
            "label_width",
            "label_height",
        ):
            if float(getattr(self, name)) <= 0:
                raise ValueError(f"{name} must be positive")
        for name in ("top_margin", "left_margin", "horizontal_gap", "vertical_gap"):
            if float(getattr(self, name)) < 0:
                raise ValueError(f"{name} must be non-negative")

    @property
    def labels_per_page(self) -> int:
        """Return ``rows * columns``."""
        return self.rows * self.columns

    @property
    def printable_width(self) -> float:
        """Return the width of the label grid in inches."""
        if self.columns <= 0:
            return 0.0
        return (
            self.columns * self.label_width + (self.columns - 1) * self.horizontal_gap
        )

    @property
    def printable_height(self) -> float:
        """Return the height of the label grid in inches."""
        if self.rows <= 0:
            return 0.0
        return self.rows * self.label_height + (self.rows - 1) * self.vertical_gap
