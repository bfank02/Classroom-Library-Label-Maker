"""Tests for GUI → WorkbookGenerationService integration (RC3.2/RC3.3)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from classroom_library_label_maker.config import load_application_settings
from classroom_library_label_maker.constants import DEFAULT_LABEL_TEMPLATE_ID
from classroom_library_label_maker.exceptions import InvalidWorkbookError
from classroom_library_label_maker.gui.app import create_application
from classroom_library_label_maker.gui.controller import GuiController
from classroom_library_label_maker.gui.main_window import MainWindow
from classroom_library_label_maker.models import (
    ApplicationSettings,
    WorkbookGenerationResult,
)
from classroom_library_label_maker.services.workbook_generation_service import (
    WorkbookGenerationService,
)
from gui_test_helpers import wait_until_generation_finished

INVENTORY = (
    Path(__file__).resolve().parent / "assets" / "workbooks" / "valid_books.xlsx"
)


@pytest.fixture(scope="module")
def qapp():
    app = create_application(["classroom-library-label-maker-gui-gen-test"])
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


class _RecordingService:
    """Test double that records generate() inputs and returns a fixed result."""

    def __init__(
        self,
        settings: ApplicationSettings,
        *,
        result: WorkbookGenerationResult | None = None,
        error: BaseException | None = None,
    ) -> None:
        self.settings = settings
        self.calls: list[dict[str, Path | None]] = []
        self._result = result or WorkbookGenerationResult(
            books_imported=2,
            books_processed=2,
            labels_created=2,
            pages_created=1,
            barcodes_generated=2,
            barcodes_reused=0,
            output_path=Path("out.xlsx"),
            elapsed_seconds=0.1,
        )
        self._error = error

    def generate(
        self,
        *,
        workbook_path: Path | None = None,
        output_path: Path | None = None,
    ) -> WorkbookGenerationResult:
        self.calls.append(
            {"workbook_path": workbook_path, "output_path": output_path}
        )
        if self._error is not None:
            raise self._error
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


def test_controller_invokes_generation_service_with_form_inputs(
    qapp, tmp_paths: dict[str, Path]
) -> None:
    window = MainWindow()
    recorded: list[_RecordingService] = []

    def factory(settings: ApplicationSettings) -> _RecordingService:
        service = _RecordingService(settings)
        recorded.append(service)
        return service

    controller = GuiController(window, generation_service_factory=factory)
    controller.set_inventory_workbook(tmp_paths["inventory"])
    controller.set_barcode_folder(tmp_paths["barcodes"])
    controller.set_output_workbook(tmp_paths["output"])

    controller.on_generate_labels()
    wait_until_generation_finished(controller)

    assert len(recorded) == 1
    service = recorded[0]
    assert service.settings.workbook_path == tmp_paths["inventory"].resolve()
    assert service.settings.barcode_output_directory == tmp_paths["barcodes"].resolve()
    assert service.settings.label_template_id == DEFAULT_LABEL_TEMPLATE_ID
    assert service.calls == [
        {
            "workbook_path": tmp_paths["inventory"].resolve(),
            "output_path": tmp_paths["output"].resolve(),
        }
    ]
    assert "generated 2 label" in window.status_label.text().lower()
    assert str(tmp_paths["output"].resolve()) in window.status_label.text()
    assert "traceback" not in window.status_label.text().lower()
    window.close()


def test_generation_failure_updates_status_without_traceback(
    qapp, tmp_paths: dict[str, Path]
) -> None:
    window = MainWindow()

    def factory(settings: ApplicationSettings) -> _RecordingService:
        return _RecordingService(
            settings,
            error=InvalidWorkbookError("Inventory workbook could not be read."),
        )

    controller = GuiController(window, generation_service_factory=factory)
    controller.set_inventory_workbook(tmp_paths["inventory"])
    controller.set_barcode_folder(tmp_paths["barcodes"])
    controller.set_output_workbook(tmp_paths["output"])

    controller.on_generate_labels()
    wait_until_generation_finished(controller)

    status = window.status_label.text()
    assert "could not be read" in status.lower()
    assert "traceback" not in status.lower()
    assert 'file "' not in status.lower()
    assert window.generate_button.isEnabled()
    window.close()


def test_unexpected_failure_hides_exception_details(
    qapp, tmp_paths: dict[str, Path]
) -> None:
    window = MainWindow()

    def factory(settings: ApplicationSettings) -> _RecordingService:
        return _RecordingService(settings, error=RuntimeError("secret boom"))

    controller = GuiController(window, generation_service_factory=factory)
    controller.set_inventory_workbook(tmp_paths["inventory"])
    controller.set_barcode_folder(tmp_paths["barcodes"])
    controller.set_output_workbook(tmp_paths["output"])

    controller.on_generate_labels()
    wait_until_generation_finished(controller)

    status = window.status_label.text().lower()
    assert "unexpectedly" in status
    assert "secret boom" not in status
    assert "traceback" not in status
    window.close()


def test_gui_generation_matches_direct_service_path(
    qapp, tmp_path: Path
) -> None:
    """GUI and direct WorkbookGenerationService produce the same summary."""
    inventory = INVENTORY
    assert inventory.is_file()

    barcodes_direct = tmp_path / "barcodes_direct"
    barcodes_gui = tmp_path / "barcodes_gui"
    barcodes_direct.mkdir()
    barcodes_gui.mkdir()
    out_direct = tmp_path / "direct_labels.xlsx"
    out_gui = tmp_path / "gui_labels.xlsx"

    direct_settings = load_application_settings(
        workbook_path=inventory,
        barcode_output_directory=barcodes_direct,
        label_template_id=DEFAULT_LABEL_TEMPLATE_ID,
        overwrite=True,
    )
    direct = WorkbookGenerationService(direct_settings).generate(
        workbook_path=inventory,
        output_path=out_direct,
    )

    gui_results: list[WorkbookGenerationResult] = []

    def factory(settings: ApplicationSettings) -> object:
        settings.overwrite = True

        class _Capturing:
            def __init__(self, inner: WorkbookGenerationService) -> None:
                self._inner = inner

            def generate(
                self,
                *,
                workbook_path: Path | None = None,
                output_path: Path | None = None,
            ) -> WorkbookGenerationResult:
                result = self._inner.generate(
                    workbook_path=workbook_path,
                    output_path=output_path,
                )
                gui_results.append(result)
                return result

        return _Capturing(WorkbookGenerationService(settings))

    window = MainWindow()
    controller = GuiController(window, generation_service_factory=factory)
    controller.set_inventory_workbook(inventory)
    controller.set_barcode_folder(barcodes_gui)
    controller.set_output_workbook(out_gui)
    controller.on_generate_labels()
    wait_until_generation_finished(controller)

    assert out_gui.is_file()
    assert out_direct.is_file()
    assert len(gui_results) == 1
    gui = gui_results[0]
    assert gui.books_imported == direct.books_imported
    assert gui.labels_created == direct.labels_created
    assert gui.pages_created == direct.pages_created
    assert sorted(p.name for p in barcodes_gui.glob("*.png")) == sorted(
        p.name for p in barcodes_direct.glob("*.png")
    )
    assert "generated" in window.status_label.text().lower()
    window.close()


def test_build_application_settings_maps_form_fields(
    qapp, tmp_paths: dict[str, Path]
) -> None:
    window = MainWindow()
    controller = GuiController(window)
    controller.set_inventory_workbook(tmp_paths["inventory"])
    controller.set_barcode_folder(tmp_paths["barcodes"])
    controller.set_output_workbook(tmp_paths["output"])

    settings = controller.build_application_settings()
    assert settings.workbook_path == tmp_paths["inventory"].resolve()
    assert settings.barcode_output_directory == tmp_paths["barcodes"].resolve()
    assert settings.label_template_id == DEFAULT_LABEL_TEMPLATE_ID
    window.close()
