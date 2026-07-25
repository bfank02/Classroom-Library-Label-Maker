"""Label layout service — arrange books onto worksheet pages.

Uses :class:`LabelTemplate` for physical grid geometry and a
:class:`LabelSheetTarget` for worksheet writes. Does not generate barcodes,
validate ISBNs, import workbooks, print, save, or display UI.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import time

from classroom_library_label_maker.exceptions import (
    ConfigurationError,
    LabelLayoutError,
)
from classroom_library_label_maker.label_templates.label_template import LabelTemplate
from classroom_library_label_maker.label_templates.template_registry import (
    TemplateRegistry,
    create_default_template_registry,
)
from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.models import (
    ApplicationSettings,
    Book,
    LabelLayoutResult,
    LabelLayoutWarning,
)
from classroom_library_label_maker.workbooks.label_sheet_target import (
    LabelPlacement,
    LabelSheetTarget,
)

_logger = get_logger("label_layout_service")


class LabelLayoutService:
    """Arrange :class:`Book` instances onto label sheets via a template.

    Responsibilities are limited to pagination and placement. Barcode PNGs are
    optional inputs; missing images become placeholders with warnings.
    """

    def __init__(
        self,
        settings: ApplicationSettings,
        *,
        registry: TemplateRegistry | None = None,
    ) -> None:
        """Initialize the layout service.

        Args:
            settings: Application settings (uses ``label_template_id`` by default).
            registry: Optional template registry override.
        """
        self._settings = settings
        self._registry = registry or create_default_template_registry()

    def layout_books(
        self,
        books: Sequence[Book],
        target: LabelSheetTarget,
        *,
        template: LabelTemplate | None = None,
        barcode_paths: Mapping[str, Path | str] | None = None,
    ) -> LabelLayoutResult:
        """Place ``books`` onto ``target`` using the selected label template.

        Args:
            books: Books to place (already imported; not validated here).
            target: Worksheet abstraction receiving placements.
            template: Optional explicit template; otherwise resolved from
                ``settings.label_template_id``.
            barcode_paths: Optional map of ISBN → barcode PNG path.

        Returns:
            Immutable :class:`LabelLayoutResult`.

        Raises:
            ConfigurationError: When the configured template id is unknown.
            LabelLayoutError: When layout fails unrecoverably.
        """
        started = time.perf_counter()
        resolved = template or self._resolve_template()
        paths = {
            str(isbn): Path(path)
            for isbn, path in (barcode_paths or {}).items()
        }

        _logger.info(
            "Label layout started: books=%s template=%s",
            len(books),
            resolved.template_id,
        )
        _logger.info("Template selected: %s (%s)", resolved.template_id, resolved.template_name)

        capacity = resolved.labels_per_page
        if capacity < 1:
            raise LabelLayoutError(
                f"Template {resolved.template_id!r} has invalid labels_per_page={capacity}"
            )

        warnings: list[LabelLayoutWarning] = []
        labels_placed = 0
        pages_created = 0
        current_page = 0

        try:
            for index, book in enumerate(books):
                page_number = (index // capacity) + 1
                slot = index % capacity
                row = slot // resolved.columns
                column = slot % resolved.columns

                if page_number != current_page:
                    target.begin_page(page_number, template=resolved)
                    pages_created += 1
                    current_page = page_number
                    _logger.info("Page created: %s", page_number)

                barcode_path, used_placeholder, warning = self._resolve_barcode(
                    book,
                    paths,
                    page_number=page_number,
                )
                if warning is not None:
                    warnings.append(warning)
                    _logger.warning("%s", warning.message)

                placement = LabelPlacement(
                    page_number=page_number,
                    row=row,
                    column=column,
                    title=book.title,
                    author=book.author,
                    isbn=book.isbn,
                    barcode_image_path=barcode_path,
                    used_placeholder_barcode=used_placeholder,
                )
                target.place_label(placement)
                labels_placed += 1
        except (ConfigurationError, LabelLayoutError):
            raise
        except Exception as exc:
            raise LabelLayoutError(
                f"Label layout failed while placing books: {exc}",
                cause=exc,
            ) from exc

        empty_remaining = 0
        if labels_placed == 0:
            empty_remaining = 0
        elif labels_placed % capacity == 0:
            empty_remaining = 0
        else:
            empty_remaining = capacity - (labels_placed % capacity)

        elapsed = time.perf_counter() - started
        result = LabelLayoutResult(
            pages_created=pages_created,
            labels_placed=labels_placed,
            empty_labels_remaining_on_last_page=empty_remaining,
            elapsed_seconds=elapsed,
            warnings=tuple(warnings),
            template_id=resolved.template_id,
        )
        _logger.info(
            "Label layout completed: pages=%s labels=%s empty_remaining=%s "
            "warnings=%s elapsed=%.3fs",
            result.pages_created,
            result.labels_placed,
            result.empty_labels_remaining_on_last_page,
            len(result.warnings),
            result.elapsed_seconds,
        )
        return result

    def _resolve_template(self) -> LabelTemplate:
        template_id = self._settings.label_template_id
        _logger.debug("Resolving label template id=%s", template_id)
        return self._registry.get(template_id)

    def _resolve_barcode(
        self,
        book: Book,
        paths: Mapping[str, Path],
        *,
        page_number: int,
    ) -> tuple[Path | None, bool, LabelLayoutWarning | None]:
        path = paths.get(book.isbn)
        if path is None:
            # Try normalized digits-only key as a convenience.
            digits = "".join(ch for ch in book.isbn if ch.isdigit())
            path = paths.get(digits) if digits else None

        if path is None:
            return (
                None,
                True,
                LabelLayoutWarning(
                    message=(
                        f"No barcode image supplied for ISBN {book.isbn!r}; "
                        "using placeholder"
                    ),
                    isbn=book.isbn,
                    page_number=page_number,
                    code="missing_barcode",
                ),
            )

        if not path.is_file():
            return (
                None,
                True,
                LabelLayoutWarning(
                    message=(
                        f"Barcode image not found for ISBN {book.isbn!r} "
                        f"at {path}; using placeholder"
                    ),
                    isbn=book.isbn,
                    page_number=page_number,
                    code="barcode_file_missing",
                ),
            )

        return path, False, None
