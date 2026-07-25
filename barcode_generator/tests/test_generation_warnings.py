"""Tests for structured generation warnings and shared completion summaries."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from classroom_library_label_maker.exceptions import InvalidWorkbookError
from classroom_library_label_maker.generation_summary import (
    cli_completion_lines,
    gui_completion_status,
)
from classroom_library_label_maker.gui.app import create_application
from classroom_library_label_maker.gui.controller import GuiController
from classroom_library_label_maker.gui.main_window import MainWindow
from classroom_library_label_maker.models import (
    ApplicationSettings,
    GenerationCompletionState,
    WorkbookGenerationResult,
    WorkbookGenerationWarning,
)
from gui_test_helpers import wait_until_generation_finished

INVENTORY = (
    Path(__file__).resolve().parent / "assets" / "workbooks" / "valid_books.xlsx"
)


@pytest.fixture(scope="module")
def qapp():
    app = create_application(["classroom-library-label-maker-gui-warnings-test"])
    yield app


@pytest.fixture
def tmp_paths(tmp_path: Path) -> dict[str, Path]:
    barcodes = tmp_path / "barcodes"
    barcodes.mkdir()
    output = tmp_path / "out" / "library_labels.xlsx"
    output.parent.mkdir()
    return {
        "inventory": INVENTORY,
        "barcodes": barcodes,
        "output": output,
    }


def _clean_result(output: Path) -> WorkbookGenerationResult:
    return WorkbookGenerationResult(
        books_imported=2,
        books_processed=2,
        labels_created=2,
        pages_created=1,
        barcodes_generated=2,
        barcodes_reused=0,
        output_path=output,
        elapsed_seconds=0.25,
    )


def _warned_result(output: Path) -> WorkbookGenerationResult:
    return WorkbookGenerationResult(
        books_imported=2,
        books_processed=2,
        labels_created=2,
        pages_created=1,
        barcodes_generated=1,
        barcodes_reused=0,
        output_path=output,
        elapsed_seconds=0.4,
        warnings=(
            WorkbookGenerationWarning(
                message="ISBN validation failed for 123",
                code="isbn_validation_failed",
                isbn="123",
            ),
            WorkbookGenerationWarning(
                message="No barcode image supplied for ISBN '123'; using placeholder",
                code="missing_barcode_image",
                isbn="123",
                page_number=1,
            ),
        ),
    )


class _FixedService:
    def __init__(
        self,
        settings: ApplicationSettings,
        *,
        result: WorkbookGenerationResult | None = None,
        error: BaseException | None = None,
    ) -> None:
        self.settings = settings
        self._result = result
        self._error = error

    def generate(
        self,
        *,
        workbook_path: Path | None = None,
        output_path: Path | None = None,
        progress_reporter=None,
    ) -> WorkbookGenerationResult:
        if self._error is not None:
            raise self._error
        assert self._result is not None
        if output_path is not None:
            return WorkbookGenerationResult(
                books_imported=self._result.books_imported,
                books_processed=self._result.books_processed,
                labels_created=self._result.labels_created,
                pages_created=self._result.pages_created,
                barcodes_generated=self._result.barcodes_generated,
                barcodes_reused=self._result.barcodes_reused,
                output_path=output_path,
                elapsed_seconds=self._result.elapsed_seconds,
                warnings=self._result.warnings,
            )
        return self._result


def test_result_completion_state_clean() -> None:
    result = _clean_result(Path("out.xlsx"))
    assert result.warning_count == 0
    assert not result.has_warnings
    assert not result.requires_review
    assert result.completion_state is GenerationCompletionState.SUCCESS
    summary = result.to_dict()["summary"]
    assert summary["warning_count"] == 0
    assert summary["requires_review"] is False
    assert summary["completion_state"] == "success"


def test_result_completion_state_with_warnings() -> None:
    result = _warned_result(Path("out.xlsx"))
    assert result.warning_count == 2
    assert result.has_warnings
    assert result.requires_review
    assert (
        result.completion_state
        is GenerationCompletionState.SUCCESS_WITH_WARNINGS
    )
    payload = result.to_dict()
    assert payload["summary"]["warning_count"] == 2
    assert payload["summary"]["requires_review"] is True
    assert payload["summary"]["completion_state"] == "success_with_warnings"
    assert len(payload["warnings"]) == 2


def test_gui_completion_status_clean() -> None:
    text = gui_completion_status(_clean_result(Path("labels.xlsx")))
    assert text.startswith("Done —")
    assert "Ready to print." in text
    assert "warning" not in text.lower()


def test_gui_completion_status_with_warnings() -> None:
    text = gui_completion_status(_warned_result(Path("labels.xlsx")))
    assert "Saved with 2 warnings" in text
    assert "review before printing" in text.lower()
    assert "Ready to print." not in text
    # Status stays concise — no per-warning dump.
    assert "ISBN validation failed" not in text


def test_cli_completion_lines_clean() -> None:
    lines = "\n".join(cli_completion_lines(_clean_result(Path("labels.xlsx"))))
    assert "Generation complete" in lines
    assert "Ready to print." in lines
    assert "Warnings" not in lines


def test_cli_completion_lines_with_warnings() -> None:
    lines = "\n".join(cli_completion_lines(_warned_result(Path("labels.xlsx"))))
    assert "Generation complete with 2 warnings" in lines
    assert "Review the workbook before printing." in lines
    assert "Warnings (2):" in lines
    assert "ISBN validation failed for 123" in lines
    assert "using placeholder" in lines


def test_gui_clean_success_status(qapp, tmp_paths: dict[str, Path]) -> None:
    window = MainWindow()
    result = _clean_result(tmp_paths["output"])

    def factory(settings: ApplicationSettings) -> _FixedService:
        return _FixedService(settings, result=result)

    controller = GuiController(window, generation_service_factory=factory)
    controller.set_inventory_workbook(tmp_paths["inventory"])
    controller.set_barcode_folder(tmp_paths["barcodes"])
    controller.set_output_workbook(tmp_paths["output"])
    controller.on_generate_labels()
    wait_until_generation_finished(controller)

    status = window.status_label.text()
    assert "done" in status.lower()
    assert "ready to print" in status.lower()
    assert "warning" not in status.lower()
    assert window.status_label.property("statusLevel") == "ok"
    window.close()


def test_gui_success_with_warnings_status(
    qapp, tmp_paths: dict[str, Path]
) -> None:
    window = MainWindow()
    result = _warned_result(tmp_paths["output"])

    def factory(settings: ApplicationSettings) -> _FixedService:
        return _FixedService(settings, result=result)

    controller = GuiController(window, generation_service_factory=factory)
    controller.set_inventory_workbook(tmp_paths["inventory"])
    controller.set_barcode_folder(tmp_paths["barcodes"])
    controller.set_output_workbook(tmp_paths["output"])
    controller.on_generate_labels()
    wait_until_generation_finished(controller)

    status = window.status_label.text().lower()
    assert "2 warnings" in status
    assert "review before printing" in status
    assert "ready to print" not in status
    assert "isbn validation failed" not in status
    assert window.status_label.property("statusLevel") == "warning"
    window.close()


def test_gui_failure_status(qapp, tmp_paths: dict[str, Path]) -> None:
    window = MainWindow()

    def factory(settings: ApplicationSettings) -> _FixedService:
        return _FixedService(
            settings,
            error=InvalidWorkbookError("Inventory workbook could not be read."),
        )

    controller = GuiController(window, generation_service_factory=factory)
    controller.set_inventory_workbook(tmp_paths["inventory"])
    controller.set_barcode_folder(tmp_paths["barcodes"])
    controller.set_output_workbook(tmp_paths["output"])
    controller.on_generate_labels()
    wait_until_generation_finished(controller)

    assert "could not be read" in window.status_label.text().lower()
    assert window.status_label.property("statusLevel") == "error"
    window.close()
