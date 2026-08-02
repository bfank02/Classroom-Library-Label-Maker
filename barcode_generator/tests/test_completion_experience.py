"""Tests for the Ready to Print completion experience (v1.4 Phase 3)."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import QApplication
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from classroom_library_label_maker.generation_summary import (
    build_gui_completion_summary,
)
from classroom_library_label_maker.gui.app import create_application
from classroom_library_label_maker.gui.controller import GuiController
from classroom_library_label_maker.gui.main_window import MainWindow
from classroom_library_label_maker.models import (
    ApplicationSettings,
    EnrichmentSummary,
    ReviewSessionResult,
    WorkbookGenerationResult,
    WorkbookGenerationWarning,
)
from gui_test_helpers import wait_until_generation_finished


@pytest.fixture(scope="module")
def qapp():
    app = create_application(["classroom-library-label-maker-gui-completion"])
    yield app


class _FixedService:
    def __init__(
        self,
        settings: ApplicationSettings,
        *,
        result: WorkbookGenerationResult,
    ) -> None:
        self.settings = settings
        self._result = result

    def generate(self, **kwargs: object) -> WorkbookGenerationResult:
        return self._result


def _result(
    output: Path,
    *,
    labels: int = 83,
    pages: int = 3,
    enrichment: EnrichmentSummary | None = None,
    warnings: tuple[WorkbookGenerationWarning, ...] = (),
) -> WorkbookGenerationResult:
    return WorkbookGenerationResult(
        books_imported=labels,
        books_processed=labels,
        labels_created=labels,
        pages_created=pages,
        barcodes_generated=labels,
        output_path=output,
        enrichment=enrichment,
        warnings=warnings,
    )


def _seed_controller(
    window: MainWindow,
    tmp_path: Path,
    result: WorkbookGenerationResult,
    *,
    open_path=None,
) -> GuiController:
    barcodes = tmp_path / "barcodes"
    barcodes.mkdir()
    inventory = tmp_path / "inventory.xlsx"
    inventory.write_text("x", encoding="utf-8")
    output = result.output_path
    assert output is not None
    output.parent.mkdir(parents=True, exist_ok=True)

    def factory(settings: ApplicationSettings) -> _FixedService:
        return _FixedService(settings, result=result)

    controller = GuiController(
        window,
        generation_service_factory=factory,
        preferences_path=tmp_path / "prefs.json",
        open_path=open_path,
    )
    controller.set_inventory_workbook(inventory)
    controller.set_barcode_folder(barcodes)
    controller.set_output_workbook(output)
    window.show()
    QApplication.processEvents()
    return controller


def test_build_gui_completion_summary_details() -> None:
    output = Path("/tmp/Test Labels Carrie.xlsx")
    inventory = Path("/tmp/Inventory (Updated ISBNs).xlsx")
    summary = build_gui_completion_summary(
        _result(
            output,
            enrichment=EnrichmentSummary(
                enabled=True,
                isbns_found=21,
                ambiguous_matches=5,
            ),
        ),
        updated_inventory_path=inventory,
        books_reviewed=5,
    )
    assert summary.headline == "✔ Ready to Print"
    assert "83 labels created" in summary.detail_lines
    assert "3 pages" in summary.detail_lines
    assert "21 ISBNs found automatically" in summary.detail_lines
    assert "5 books reviewed" in summary.detail_lines
    assert summary.label_workbook_name == "Test Labels Carrie.xlsx"
    assert summary.updated_inventory_name == "Inventory (Updated ISBNs).xlsx"
    assert summary.requires_attention is False


def test_completion_view_after_generation(qapp, tmp_path: Path) -> None:
    output = tmp_path / "out" / "Test Labels Carrie.xlsx"
    window = MainWindow()
    controller = _seed_controller(
        window,
        tmp_path,
        _result(
            output,
            enrichment=EnrichmentSummary(enabled=True, isbns_found=21),
        ),
    )
    controller.on_generate_labels()
    wait_until_generation_finished(controller)

    assert window.is_showing_completion() is True
    assert window.generate_button.isVisible() is False
    view = window.completion_view
    assert "Ready to Print" in view.headline_label.text()
    details = view.details_label.text()
    assert "83 labels created" in details
    assert "3 pages" in details
    assert "21 ISBNs found automatically" in details
    assert view.label_file_name.text() == "Test Labels Carrie.xlsx"
    assert view.inventory_file_block.isHidden() is True
    assert view.open_inventory_button.isHidden() is True
    assert view.done_button.isVisible() is True
    window.close()


def test_updated_inventory_shown_conditionally(qapp, tmp_path: Path) -> None:
    output = tmp_path / "out" / "labels.xlsx"
    inventory_out = tmp_path / "Inventory (Updated ISBNs).xlsx"
    window = MainWindow()
    controller = _seed_controller(window, tmp_path, _result(output))
    controller._last_review_result = ReviewSessionResult(
        resolved_count=2,
        skipped_count=1,
        total_reviewed=3,
    )
    controller._last_manual_isbn_count = 2
    controller._show_ready_to_print(
        _result(output),
        inventory_out,
    )
    window.show()
    QApplication.processEvents()

    view = window.completion_view
    assert window.is_showing_completion()
    assert view.inventory_file_block.isVisible() is True
    assert view.inventory_file_name.text() == inventory_out.name
    assert view.open_inventory_button.isVisible() is True
    assert "2 ISBNs entered manually" in view.details_label.text()
    assert "1 label intentionally skipped" in view.details_label.text()
    window.close()


def test_done_returns_to_home_and_preserves_settings(
    qapp, tmp_path: Path
) -> None:
    output = tmp_path / "out" / "labels.xlsx"
    window = MainWindow()
    controller = _seed_controller(window, tmp_path, _result(output, labels=2, pages=1))
    inventory = controller._state.inventory_workbook
    barcodes = controller._state.barcode_folder
    folder = controller._state.label_folder
    filename = controller._state.label_filename
    template = controller._state.label_template_id

    controller.on_generate_labels()
    wait_until_generation_finished(controller)
    assert window.is_showing_completion()

    window.completion_view.done_button.click()
    QApplication.processEvents()

    assert window.is_showing_completion() is False
    assert window.stack.currentWidget() is window.home_page
    assert window.completion_view.summary() is None
    assert "ready to generate" in window.status_label.text().lower()
    assert controller._state.inventory_workbook == inventory
    assert controller._state.barcode_folder == barcodes
    assert controller._state.label_folder == folder
    assert controller._state.label_filename == filename
    assert controller._state.label_template_id == template
    assert window.generate_button.isEnabled() is True
    window.close()


def test_open_label_workbook_action(qapp, tmp_path: Path) -> None:
    output = tmp_path / "out" / "labels.xlsx"
    opened: list[Path] = []
    window = MainWindow()
    controller = _seed_controller(
        window,
        tmp_path,
        _result(output, labels=1, pages=1),
        open_path=opened.append,
    )
    controller.on_generate_labels()
    wait_until_generation_finished(controller)

    window.completion_view.open_label_button.click()
    QApplication.processEvents()
    assert opened == [output]
    window.close()


def test_open_updated_inventory_action(qapp, tmp_path: Path) -> None:
    output = tmp_path / "out" / "labels.xlsx"
    inventory_out = tmp_path / "Inventory (Updated ISBNs).xlsx"
    opened: list[Path] = []
    window = MainWindow()
    controller = _seed_controller(
        window,
        tmp_path,
        _result(output, labels=1, pages=1),
        open_path=opened.append,
    )
    controller._show_ready_to_print(_result(output, labels=1, pages=1), inventory_out)
    QApplication.processEvents()

    window.completion_view.open_inventory_button.click()
    QApplication.processEvents()
    assert opened == [inventory_out]
    window.close()


def test_warnings_still_use_completion_view(qapp, tmp_path: Path) -> None:
    output = tmp_path / "out" / "labels.xlsx"
    window = MainWindow()
    result = _result(
        output,
        labels=2,
        pages=1,
        warnings=(
            WorkbookGenerationWarning(
                message="ISBN validation failed",
                code="isbn_validation_failed",
            ),
            WorkbookGenerationWarning(message="other", code="other"),
        ),
    )
    controller = _seed_controller(window, tmp_path, result)
    controller.on_generate_labels()
    wait_until_generation_finished(controller)

    assert window.is_showing_completion()
    details = window.completion_view.details_label.text().lower()
    assert "2 warnings" in details
    assert "review before printing" in details
    assert window.completion_view.summary() is not None
    assert window.completion_view.summary().requires_attention is True
    window.close()
