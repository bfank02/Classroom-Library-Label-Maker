"""Tests for GUI progress forwarding (RC3.4)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from PySide6.QtTest import QSignalSpy
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
from classroom_library_label_maker.progress import (
    GenerationProgress,
    GenerationStage,
)
from gui_test_helpers import wait_until_generation_finished

INVENTORY = (
    Path(__file__).resolve().parent / "assets" / "workbooks" / "valid_books.xlsx"
)


@pytest.fixture(scope="module")
def qapp():
    app = create_application(["classroom-library-label-maker-gui-progress-test"])
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


def test_worker_forwards_progress_events(qapp, tmp_paths: dict[str, Path]) -> None:
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
            def generate(
                self,
                *,
                workbook_path=None,
                output_path=None,
                progress_reporter=None,
            ):
                assert progress_reporter is not None
                progress_reporter.on_progress(
                    GenerationProgress.for_stage(GenerationStage.IMPORTING)
                )
                progress_reporter.on_progress(
                    GenerationProgress.for_stage(GenerationStage.SAVING)
                )
                return WorkbookGenerationResult(
                    labels_created=1,
                    pages_created=1,
                    output_path=output_path,
                )

        return Stub()

    worker = GenerationWorker(job, service_factory=factory)
    progress_spy = QSignalSpy(worker.progress)
    completed_spy = QSignalSpy(worker.completed)
    worker.run()

    assert completed_spy.count() == 1
    assert progress_spy.count() == 2
    first = progress_spy.at(0)[0]
    second = progress_spy.at(1)[0]
    assert isinstance(first, GenerationProgress)
    assert first.stage is GenerationStage.IMPORTING
    assert second.stage is GenerationStage.SAVING


def test_controller_updates_status_from_progress(
    qapp, tmp_paths: dict[str, Path]
) -> None:
    window = MainWindow()
    seen: list[str] = []

    def factory(_settings: ApplicationSettings) -> object:
        class Stub:
            def generate(
                self,
                *,
                workbook_path=None,
                output_path=None,
                progress_reporter=None,
            ):
                assert progress_reporter is not None
                for stage in (
                    GenerationStage.IMPORTING,
                    GenerationStage.CREATING_LABELS,
                    GenerationStage.SAVING,
                ):
                    progress_reporter.on_progress(
                        GenerationProgress.for_stage(stage)
                    )
                    time.sleep(0.05)
                return WorkbookGenerationResult(
                    labels_created=2,
                    pages_created=1,
                    output_path=output_path,
                )

        return Stub()

    controller = GuiController(window, generation_service_factory=factory)
    controller.set_inventory_workbook(tmp_paths["inventory"])
    controller.set_barcode_folder(tmp_paths["barcodes"])
    controller.set_output_workbook(tmp_paths["output"])

    controller.on_generate_labels()
    waited = 0
    while controller.is_generating and waited < 5000:
        text = window.status_label.text()
        if text and (not seen or seen[-1] != text):
            seen.append(text)
        QApplication.processEvents()
        waited += 20
        from PySide6.QtTest import QTest

        QTest.qWait(20)

    wait_until_generation_finished(controller)
    assert any("Importing workbook" in item for item in seen)
    assert window.is_showing_completion()
    assert "2 labels" in window.completion_view.details_label.text().lower()
    window.close()


def test_completion_replaces_progress_message(
    qapp, tmp_paths: dict[str, Path]
) -> None:
    window = MainWindow()

    def factory(_settings: ApplicationSettings) -> object:
        class Stub:
            def generate(
                self,
                *,
                workbook_path=None,
                output_path=None,
                progress_reporter=None,
            ):
                if progress_reporter is not None:
                    progress_reporter.on_progress(
                        GenerationProgress.for_stage(GenerationStage.SAVING)
                    )
                return WorkbookGenerationResult(
                    labels_created=1,
                    pages_created=1,
                    output_path=output_path,
                )

        return Stub()

    controller = GuiController(window, generation_service_factory=factory)
    controller.set_inventory_workbook(tmp_paths["inventory"])
    controller.set_barcode_folder(tmp_paths["barcodes"])
    controller.set_output_workbook(tmp_paths["output"])
    controller.on_generate_labels()
    wait_until_generation_finished(controller)

    assert window.is_showing_completion()
    assert "saving workbook" not in window.status_label.text().lower()
    assert "1 label" in window.completion_view.details_label.text().lower()
    window.close()


def test_failure_replaces_progress_message(
    qapp, tmp_paths: dict[str, Path]
) -> None:
    window = MainWindow()

    def factory(_settings: ApplicationSettings) -> object:
        class Stub:
            def generate(
                self,
                *,
                workbook_path=None,
                output_path=None,
                progress_reporter=None,
            ):
                if progress_reporter is not None:
                    progress_reporter.on_progress(
                        GenerationProgress.for_stage(GenerationStage.IMPORTING)
                    )
                raise InvalidWorkbookError("Inventory workbook could not be read.")

        return Stub()

    controller = GuiController(window, generation_service_factory=factory)
    controller.set_inventory_workbook(tmp_paths["inventory"])
    controller.set_barcode_folder(tmp_paths["barcodes"])
    controller.set_output_workbook(tmp_paths["output"])
    controller.on_generate_labels()
    wait_until_generation_finished(controller)

    assert "importing workbook" not in window.status_label.text().lower()
    assert "could not be read" in window.status_label.text().lower()
    window.close()
