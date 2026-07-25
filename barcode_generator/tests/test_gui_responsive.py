"""Tests for responsive background generation (RC3.3)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from classroom_library_label_maker.config import load_application_settings
from classroom_library_label_maker.constants import DEFAULT_LABEL_TEMPLATE_ID
from classroom_library_label_maker.exceptions import InvalidWorkbookError
from classroom_library_label_maker.gui.app import create_application
from classroom_library_label_maker.gui.controller import GuiController
from classroom_library_label_maker.gui.generation_worker import (
    GenerationJob,
    GenerationWorker,
)
from classroom_library_label_maker.gui.main_window import MainWindow
from classroom_library_label_maker.models import (
    ApplicationSettings,
    WorkbookGenerationResult,
)
from gui_test_helpers import wait_until_generation_finished

INVENTORY = (
    Path(__file__).resolve().parent / "assets" / "workbooks" / "valid_books.xlsx"
)


@pytest.fixture(scope="module")
def qapp():
    app = create_application(["classroom-library-label-maker-gui-responsive-test"])
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


def _ready_controller(
    window: MainWindow,
    tmp_paths: dict[str, Path],
    *,
    factory: object,
) -> GuiController:
    controller = GuiController(window, generation_service_factory=factory)  # type: ignore[arg-type]
    controller.set_inventory_workbook(tmp_paths["inventory"])
    controller.set_barcode_folder(tmp_paths["barcodes"])
    controller.set_output_workbook(tmp_paths["output"])
    return controller


def _wait_until_generating(controller: GuiController, *, timeout_ms: int = 5000) -> None:
    waited = 0
    while not controller.is_generating and waited < timeout_ms:
        QApplication.processEvents()
        QTest.qWait(20)
        waited += 20
    assert controller.is_generating, "generation did not start in time"


def test_generation_worker_emits_completed(qapp, tmp_paths: dict[str, Path]) -> None:
    settings = load_application_settings(
        workbook_path=tmp_paths["inventory"],
        barcode_output_directory=tmp_paths["barcodes"],
        label_template_id=DEFAULT_LABEL_TEMPLATE_ID,
    )
    job = GenerationJob(
        settings=settings,
        workbook_path=tmp_paths["inventory"],
        output_path=tmp_paths["output"],
    )

    def factory(_settings: ApplicationSettings) -> object:
        class Stub:
            def generate(self, *, workbook_path=None, output_path=None, progress_reporter=None):
                return WorkbookGenerationResult(
                    labels_created=3,
                    pages_created=1,
                    output_path=output_path,
                )

        return Stub()

    worker = GenerationWorker(job, service_factory=factory)
    completed = QSignalSpy(worker.completed)
    failed = QSignalSpy(worker.failed)
    worker.run()

    assert failed.count() == 0
    assert completed.count() == 1
    result = completed.at(0)[0]
    assert isinstance(result, WorkbookGenerationResult)
    assert result.labels_created == 3


def test_generation_worker_emits_failed(qapp, tmp_paths: dict[str, Path]) -> None:
    settings = load_application_settings(
        workbook_path=tmp_paths["inventory"],
        barcode_output_directory=tmp_paths["barcodes"],
        label_template_id=DEFAULT_LABEL_TEMPLATE_ID,
    )
    job = GenerationJob(
        settings=settings,
        workbook_path=tmp_paths["inventory"],
        output_path=tmp_paths["output"],
    )

    def factory(_settings: ApplicationSettings) -> object:
        class Stub:
            def generate(self, *, workbook_path=None, output_path=None, progress_reporter=None):
                raise InvalidWorkbookError("bad workbook")

        return Stub()

    worker = GenerationWorker(job, service_factory=factory)
    completed = QSignalSpy(worker.completed)
    failed = QSignalSpy(worker.failed)
    worker.run()

    assert completed.count() == 0
    assert failed.count() == 1
    assert isinstance(failed.at(0)[0], InvalidWorkbookError)


def test_controls_disabled_during_generation_and_restored_on_success(
    qapp, tmp_paths: dict[str, Path]
) -> None:
    window = MainWindow()

    def factory(_settings: ApplicationSettings) -> object:
        class Slow:
            def generate(self, *, workbook_path=None, output_path=None, progress_reporter=None):
                time.sleep(0.25)
                return WorkbookGenerationResult(
                    labels_created=1,
                    pages_created=1,
                    output_path=output_path,
                )

        return Slow()

    controller = _ready_controller(window, tmp_paths, factory=factory)
    controller.on_generate_labels()
    _wait_until_generating(controller)

    assert "generating labels" in window.status_label.text().lower()
    assert not window.generate_button.isEnabled()
    assert not window.inventory_browse_button.isEnabled()
    assert not window.barcode_browse_button.isEnabled()
    assert not window.output_browse_button.isEnabled()
    assert not window.label_template_combo.isEnabled()

    wait_until_generation_finished(controller)

    assert window.generate_button.isEnabled()
    assert window.inventory_browse_button.isEnabled()
    assert window.barcode_browse_button.isEnabled()
    assert window.output_browse_button.isEnabled()
    assert window.label_template_combo.isEnabled()
    assert "1 label" in window.status_label.text().lower()
    assert "done" in window.status_label.text().lower()
    window.close()


def test_controls_restored_after_failure(
    qapp, tmp_paths: dict[str, Path]
) -> None:
    window = MainWindow()

    def factory(_settings: ApplicationSettings) -> object:
        class SlowFail:
            def generate(self, *, workbook_path=None, output_path=None, progress_reporter=None):
                time.sleep(0.25)
                raise InvalidWorkbookError("Inventory workbook could not be read.")

        return SlowFail()

    controller = _ready_controller(window, tmp_paths, factory=factory)
    controller.on_generate_labels()
    _wait_until_generating(controller)
    assert not window.generate_button.isEnabled()

    wait_until_generation_finished(controller)

    assert window.generate_button.isEnabled()
    assert window.inventory_browse_button.isEnabled()
    assert "could not be read" in window.status_label.text().lower()
    window.close()


def test_duplicate_generate_ignored_while_running(
    qapp, tmp_paths: dict[str, Path]
) -> None:
    window = MainWindow()
    calls = {"count": 0}

    def factory(_settings: ApplicationSettings) -> object:
        class Slow:
            def generate(self, *, workbook_path=None, output_path=None, progress_reporter=None):
                calls["count"] += 1
                time.sleep(0.25)
                return WorkbookGenerationResult(
                    labels_created=1,
                    pages_created=1,
                    output_path=output_path,
                )

        return Slow()

    controller = _ready_controller(window, tmp_paths, factory=factory)
    controller.on_generate_labels()
    _wait_until_generating(controller)

    controller.on_generate_labels()
    controller.on_generate_labels()
    QTest.qWait(50)
    QApplication.processEvents()

    wait_until_generation_finished(controller)
    assert calls["count"] == 1
    window.close()
