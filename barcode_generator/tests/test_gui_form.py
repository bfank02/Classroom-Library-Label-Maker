"""Tests for GUI form state, controller validation, and main window input UI."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from classroom_library_label_maker.constants import DEFAULT_LABEL_TEMPLATE_ID
from classroom_library_label_maker.gui.app import create_application, create_main_window
from classroom_library_label_maker.gui.controller import (
    GuiController,
    template_display_name,
)
from classroom_library_label_maker.gui.form_state import GenerationFormState
from classroom_library_label_maker.gui.main_window import MainWindow
from classroom_library_label_maker.label_templates import (
    AVERY_5160,
    create_default_template_registry,
)


@pytest.fixture(scope="module")
def qapp():
    app = create_application(["classroom-library-label-maker-gui-form-test"])
    yield app


@pytest.fixture
def tmp_paths(tmp_path: Path) -> dict[str, Path]:
    inventory = tmp_path / "inventory.xlsx"
    inventory.write_bytes(b"PK\x03\x04")  # minimal bytes; existence matters
    barcodes = tmp_path / "barcodes"
    barcodes.mkdir()
    output = tmp_path / "out" / "library_labels.xlsx"
    output.parent.mkdir()
    return {
        "inventory": inventory,
        "barcodes": barcodes,
        "output": output,
    }


def test_form_state_invalid_when_empty() -> None:
    state = GenerationFormState()
    messages = state.validation_messages()
    assert not state.is_valid
    assert any("inventory" in m.lower() for m in messages)
    assert any("barcode" in m.lower() for m in messages)
    assert any("save" in m.lower() for m in messages)
    assert any("template" in m.lower() for m in messages)


def test_form_state_valid_with_existing_paths(tmp_paths: dict[str, Path]) -> None:
    state = GenerationFormState(
        inventory_workbook=tmp_paths["inventory"],
        barcode_folder=tmp_paths["barcodes"],
        output_workbook=tmp_paths["output"],
        label_template_id=DEFAULT_LABEL_TEMPLATE_ID,
    )
    assert state.is_valid
    assert state.validation_messages() == ()


def test_form_state_rejects_missing_inventory(tmp_paths: dict[str, Path]) -> None:
    state = GenerationFormState(
        inventory_workbook=tmp_paths["inventory"].with_name("missing.xlsx"),
        barcode_folder=tmp_paths["barcodes"],
        output_workbook=tmp_paths["output"],
        label_template_id=DEFAULT_LABEL_TEMPLATE_ID,
    )
    assert not state.is_valid
    assert any("could not be found" in m.lower() for m in state.validation_messages())


def test_form_state_rejects_non_excel_output(tmp_paths: dict[str, Path]) -> None:
    state = GenerationFormState(
        inventory_workbook=tmp_paths["inventory"],
        barcode_folder=tmp_paths["barcodes"],
        output_workbook=tmp_paths["output"].with_suffix(".txt"),
        label_template_id=DEFAULT_LABEL_TEMPLATE_ID,
    )
    assert not state.is_valid
    assert any(".xlsx" in m for m in state.validation_messages())


def test_template_display_name_short() -> None:
    assert template_display_name(AVERY_5160) == "Avery 5160"


def test_main_window_builds_input_controls(qapp) -> None:
    window = MainWindow()
    assert window.findChild(object, "inventoryBrowseButton") is not None
    assert window.findChild(object, "barcodeBrowseButton") is not None
    assert window.findChild(object, "outputBrowseButton") is not None
    assert window.findChild(object, "labelTemplateCombo") is not None
    assert window.findChild(object, "generateButton") is not None
    assert window.findChild(object, "statusLabel") is not None
    assert window.findChild(object, "guiPlaceholderLabel") is None
    assert not window.generate_button.isEnabled()
    window.close()


def test_controller_defaults_template_and_disables_generate(qapp) -> None:
    window = MainWindow()
    controller = GuiController(window)
    assert controller.state.label_template_id == DEFAULT_LABEL_TEMPLATE_ID
    assert window.label_template_combo.currentText() == "Avery 5160"
    assert not window.generate_button.isEnabled()
    assert "inventory" in window.status_label.text().lower()
    window.close()


def test_controller_path_updates_enable_generate(
    qapp, tmp_paths: dict[str, Path]
) -> None:
    window = MainWindow()
    controller = GuiController(window)

    controller.set_inventory_workbook(tmp_paths["inventory"])
    assert tmp_paths["inventory"].name in window.inventory_path_label.text()
    assert not window.generate_button.isEnabled()

    controller.set_barcode_folder(tmp_paths["barcodes"])
    controller.set_output_workbook(tmp_paths["output"])
    assert window.generate_button.isEnabled()
    assert "ready" in window.status_label.text().lower()
    window.close()


def test_controller_browse_dialogs_update_paths(
    qapp, tmp_paths: dict[str, Path]
) -> None:
    window = MainWindow()
    controller = GuiController(
        window,
        open_inventory_dialog=lambda: tmp_paths["inventory"],
        open_barcode_folder_dialog=lambda: tmp_paths["barcodes"],
        save_output_dialog=lambda: tmp_paths["output"],
    )

    controller.browse_inventory_workbook()
    controller.browse_barcode_folder()
    controller.browse_output_workbook()

    assert controller.state.inventory_workbook == tmp_paths["inventory"].resolve()
    assert controller.state.barcode_folder == tmp_paths["barcodes"].resolve()
    assert controller.state.output_workbook == tmp_paths["output"].resolve()
    assert window.generate_button.isEnabled()
    window.close()


def test_controller_template_selection(qapp) -> None:
    window = MainWindow()
    registry = create_default_template_registry()
    controller = GuiController(window, template_registry=registry)

    window.label_template_combo.setCurrentIndex(0)
    assert controller.state.label_template_id == DEFAULT_LABEL_TEMPLATE_ID

    controller.set_label_template_id(None)
    assert not controller.state.is_valid
    assert not window.generate_button.isEnabled()
    window.close()


def test_generate_labels_uses_injected_service(
    qapp, tmp_paths: dict[str, Path]
) -> None:
    from classroom_library_label_maker.models import (
        ApplicationSettings,
        WorkbookGenerationResult,
    )
    from gui_test_helpers import wait_until_generation_finished

    window = MainWindow()
    calls: list[object] = []

    class Stub:
        def __init__(self, settings: ApplicationSettings) -> None:
            self.settings = settings

        def generate(self, *, workbook_path=None, output_path=None, progress_reporter=None):
            calls.append((workbook_path, output_path))
            return WorkbookGenerationResult(
                labels_created=1,
                pages_created=1,
                output_path=output_path,
            )

    controller = GuiController(window, generation_service_factory=Stub)
    controller.set_inventory_workbook(tmp_paths["inventory"])
    controller.set_barcode_folder(tmp_paths["barcodes"])
    controller.set_output_workbook(tmp_paths["output"])
    controller.on_generate_labels()
    wait_until_generation_finished(controller)

    assert calls == [
        (tmp_paths["inventory"].resolve(), tmp_paths["output"].resolve())
    ]
    assert "1 label" in window.status_label.text().lower()
    assert "done" in window.status_label.text().lower()
    window.close()


def test_create_main_window_wires_controller(qapp) -> None:
    window = create_main_window()
    assert isinstance(window, MainWindow)
    assert window.label_template_combo.count() >= 1
    assert window.generate_button.isEnabled() is False
    window.close()


def test_label_content_checkboxes_flow_into_settings(
    qapp, tmp_paths: dict[str, Path]
) -> None:
    window = MainWindow()
    controller = GuiController(window)
    controller.set_inventory_workbook(tmp_paths["inventory"])
    controller.set_barcode_folder(tmp_paths["barcodes"])
    controller.set_output_workbook(tmp_paths["output"])

    assert window.show_title_checkbox.isChecked()
    assert window.show_author_checkbox.isChecked()
    assert window.show_barcode_checkbox.isChecked()

    window.show_author_checkbox.setChecked(False)
    settings = controller.build_application_settings()
    assert settings.label_content.show_title is True
    assert settings.label_content.show_author is False
    assert settings.label_content.show_barcode is True
    window.close()
