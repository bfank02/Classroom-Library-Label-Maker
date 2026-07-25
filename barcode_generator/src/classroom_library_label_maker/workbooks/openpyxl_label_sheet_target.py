"""openpyxl-backed :class:`LabelSheetTarget` (placement + sheet presentation).

Vendor types stay inside this module. The layout service only sees
:class:`LabelPlacement` and :class:`LabelTemplate`. Persisting the workbook is
handled by :class:`OpenPyxlWorkbookWriter` / :class:`WorkbookWriter`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from classroom_library_label_maker.label_templates.label_template import LabelTemplate
from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.workbooks.label_sheet_target import LabelPlacement
from classroom_library_label_maker.workbooks.workbook_presentation import (
    apply_worksheet_presentation,
    label_body_alignment,
    label_body_font,
    label_title_alignment,
    label_title_font,
)

_logger = get_logger("workbooks.openpyxl_label_sheet")

# Approximate Excel character-width units per inch (implementation detail).
_COL_WIDTH_PER_INCH = 12.0
_ROW_HEIGHT_POINTS_PER_INCH = 72.0
# openpyxl / Excel treat drawing widths/heights as pixels at ~96 DPI.
_EXCEL_IMAGE_DPI = 96.0

# Vertical share of each 1-inch Avery label (must sum to 1.0).
# Barcode needs most of the height; oversized images previously spilled into
# the labels below and hid title/author text.
_LABEL_ROW_FRACTIONS: tuple[float, float, float, float] = (
    0.18,  # title
    0.15,  # author
    0.12,  # ISBN
    0.55,  # barcode
)

# Consistent sheet title prefix (page number appended).
LABEL_SHEET_PREFIX = "Labels "


class OpenPyxlLabelSheetTarget:
    """Place labels onto openpyxl worksheets with print-ready presentation."""

    def __init__(self) -> None:
        """Create an empty workbook ready for label pages."""
        try:
            from openpyxl import Workbook
        except ImportError as exc:  # pragma: no cover - dependency is required
            raise RuntimeError("openpyxl is required for OpenPyxlLabelSheetTarget") from exc

        self._workbook = Workbook()
        # Remove the default sheet; pages are created via begin_page.
        default = self._workbook.active
        if default is not None:
            self._workbook.remove(default)
        self._sheets: dict[int, Any] = {}
        self._template: LabelTemplate | None = None

    @property
    def workbook(self) -> Any:
        """Return the underlying openpyxl workbook."""
        return self._workbook

    @property
    def label_template(self) -> LabelTemplate | None:
        """Return the template used for the most recent page, if any."""
        return self._template

    def begin_page(self, page_number: int, *, template: LabelTemplate) -> None:
        """Create a worksheet for ``page_number`` sized from ``template``."""
        if page_number < 1:
            raise ValueError("page_number must be >= 1")
        if page_number in self._sheets:
            raise ValueError(f"Page {page_number} already exists")

        self._template = template
        title = f"{LABEL_SHEET_PREFIX}{page_number}"
        sheet = self._workbook.create_sheet(title=title)
        self._sheets[page_number] = sheet
        self._apply_page_geometry(sheet, template)
        apply_worksheet_presentation(sheet, template)
        _logger.debug("Created worksheet %r for page %s", title, page_number)

    def place_label(self, placement: LabelPlacement) -> None:
        """Write centered title/author/ISBN (and optional barcode) into a cell block."""
        if self._template is None:
            raise RuntimeError("begin_page must be called before place_label")
        sheet = self._sheets.get(placement.page_number)
        if sheet is None:
            raise RuntimeError(
                f"place_label called for page {placement.page_number} before begin_page"
            )

        template = self._template
        # Each logical label maps to a 4-row x 1-col block of worksheet cells.
        block_rows = 4
        start_row = placement.row * block_rows + 1
        start_col = placement.column + 1

        title_cell = sheet.cell(
            row=start_row, column=start_col, value=placement.title
        )
        title_cell.alignment = label_title_alignment()
        title_cell.font = label_title_font()

        author_cell = sheet.cell(
            row=start_row + 1, column=start_col, value=placement.author
        )
        author_cell.alignment = label_body_alignment()
        author_cell.font = label_body_font()

        isbn_cell = sheet.cell(
            row=start_row + 2, column=start_col, value=placement.isbn
        )
        isbn_cell.alignment = label_body_alignment()
        isbn_cell.font = label_body_font()

        if placement.used_placeholder_barcode or placement.barcode_image_path is None:
            barcode_cell = sheet.cell(
                row=start_row + 3,
                column=start_col,
                value="[barcode placeholder]",
            )
            barcode_cell.alignment = label_body_alignment()
            barcode_cell.font = label_body_font()
        else:
            sheet.cell(row=start_row + 3, column=start_col, value="")

        if (
            placement.barcode_image_path is not None
            and not placement.used_placeholder_barcode
            and Path(placement.barcode_image_path).is_file()
        ):
            self._add_barcode_image(
                sheet,
                path=Path(placement.barcode_image_path),
                anchor_row=start_row + 3,
                anchor_col=start_col,
                template=template,
            )

    def _apply_page_geometry(self, sheet: Any, template: LabelTemplate) -> None:
        for col_index in range(1, template.columns + 1):
            letter = self._column_letter(col_index)
            sheet.column_dimensions[letter].width = (
                template.label_width * _COL_WIDTH_PER_INCH
            )
        # Four worksheet rows per label slot with uneven heights so the barcode
        # fits inside its own label instead of covering the next row's text.
        for label_row in range(template.rows):
            for offset, fraction in enumerate(_LABEL_ROW_FRACTIONS):
                ws_row = label_row * 4 + offset + 1
                sheet.row_dimensions[ws_row].height = (
                    template.label_height * fraction * _ROW_HEIGHT_POINTS_PER_INCH
                )

    def _add_barcode_image(
        self,
        sheet: Any,
        *,
        path: Path,
        anchor_row: int,
        anchor_col: int,
        template: LabelTemplate,
    ) -> None:
        try:
            from openpyxl.drawing.image import Image as XLImage
        except ImportError:  # pragma: no cover
            _logger.warning("openpyxl.drawing.image unavailable; skipping barcode image")
            return

        image = XLImage(str(path))
        max_width_px = int(template.label_width * _EXCEL_IMAGE_DPI * 0.92)
        max_height_px = int(
            template.label_height
            * _LABEL_ROW_FRACTIONS[3]
            * _EXCEL_IMAGE_DPI
            * 0.92
        )
        self._fit_image_within(image, max_width_px, max_height_px)
        image.anchor = f"{self._column_letter(anchor_col)}{anchor_row}"
        sheet.add_image(image)

    @staticmethod
    def _fit_image_within(image: Any, max_width_px: int, max_height_px: int) -> None:
        """Scale ``image`` to fit inside a width×height box (aspect preserved)."""
        width = float(getattr(image, "width", 0) or 0)
        height = float(getattr(image, "height", 0) or 0)
        if width <= 0 or height <= 0:
            return
        ratio = min(max_width_px / width, max_height_px / height, 1.0)
        image.width = max(1, int(width * ratio))
        image.height = max(1, int(height * ratio))

    @staticmethod
    def _column_letter(index: int) -> str:
        from openpyxl.utils import get_column_letter

        return get_column_letter(index)
