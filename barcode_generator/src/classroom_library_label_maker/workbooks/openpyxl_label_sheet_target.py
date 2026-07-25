"""openpyxl-backed :class:`LabelSheetTarget` (no workbook save).

Vendor types stay inside this module. The layout service only sees
:class:`LabelPlacement` and :class:`LabelTemplate`. Callers that need a file
on disk must save the workbook themselves in a later sprint.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from classroom_library_label_maker.label_templates.label_template import LabelTemplate
from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.workbooks.label_sheet_target import LabelPlacement

_logger = get_logger("workbooks.openpyxl_label_sheet")

# Approximate Excel character-width units per inch (implementation detail).
_COL_WIDTH_PER_INCH = 12.0
_ROW_HEIGHT_POINTS_PER_INCH = 72.0


class OpenPyxlLabelSheetTarget:
    """Place labels onto openpyxl worksheets without saving the workbook."""

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
        """Return the underlying openpyxl workbook (for future save adapters)."""
        return self._workbook

    def begin_page(self, page_number: int, *, template: LabelTemplate) -> None:
        """Create a worksheet for ``page_number`` sized from ``template``."""
        if page_number < 1:
            raise ValueError("page_number must be >= 1")
        if page_number in self._sheets:
            raise ValueError(f"Page {page_number} already exists")

        self._template = template
        title = f"Labels {page_number}"
        sheet = self._workbook.create_sheet(title=title)
        self._sheets[page_number] = sheet
        self._apply_page_geometry(sheet, template)
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

        lines = [
            placement.title,
            placement.author,
            placement.isbn,
        ]
        if placement.used_placeholder_barcode or placement.barcode_image_path is None:
            lines.append("[barcode placeholder]")
        else:
            lines.append("")  # image occupies visual space below text

        for offset, text in enumerate(lines):
            cell = sheet.cell(row=start_row + offset, column=start_col, value=text)
            cell.alignment = self._center_alignment()

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
        # 4 worksheet rows per label slot for text + barcode line.
        total_ws_rows = template.rows * 4
        row_height = (template.label_height / 4.0) * _ROW_HEIGHT_POINTS_PER_INCH
        for row_index in range(1, total_ws_rows + 1):
            sheet.row_dimensions[row_index].height = row_height

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
        # Scale roughly to label width (pixels at ~96 DPI heuristic).
        max_width_px = int(template.label_width * 96 * 0.9)
        if image.width and image.width > max_width_px:
            ratio = max_width_px / float(image.width)
            image.width = max_width_px
            image.height = int(image.height * ratio)
        image.anchor = f"{self._column_letter(anchor_col)}{anchor_row}"
        sheet.add_image(image)

    @staticmethod
    def _center_alignment() -> Any:
        from openpyxl.styles import Alignment

        return Alignment(horizontal="center", vertical="center", wrap_text=True)

    @staticmethod
    def _column_letter(index: int) -> str:
        from openpyxl.utils import get_column_letter

        return get_column_letter(index)
