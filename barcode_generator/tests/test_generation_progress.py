"""Tests for Qt-independent generation progress reporting."""

from __future__ import annotations

from pathlib import Path

import pytest

from classroom_library_label_maker.config import load_application_settings
from classroom_library_label_maker.constants import DEFAULT_LABEL_TEMPLATE_ID
from classroom_library_label_maker.progress import (
    GenerationProgress,
    GenerationStage,
)
from classroom_library_label_maker.services.workbook_generation_service import (
    WorkbookGenerationService,
)

INVENTORY = (
    Path(__file__).resolve().parent / "assets" / "workbooks" / "valid_books.xlsx"
)


class _RecordingReporter:
    def __init__(self) -> None:
        self.events: list[GenerationProgress] = []

    def on_progress(self, progress: GenerationProgress) -> None:
        self.events.append(progress)


def test_generation_progress_for_stage_messages() -> None:
    progress = GenerationProgress.for_stage(GenerationStage.IMPORTING)
    assert progress.stage is GenerationStage.IMPORTING
    assert progress.message == "Importing workbook..."


def test_workbook_generation_emits_stages_in_order(tmp_path: Path) -> None:
    barcodes = tmp_path / "barcodes"
    barcodes.mkdir()
    output = tmp_path / "labels.xlsx"
    settings = load_application_settings(
        workbook_path=INVENTORY,
        barcode_output_directory=barcodes,
        label_template_id=DEFAULT_LABEL_TEMPLATE_ID,
        overwrite=True,
    )
    reporter = _RecordingReporter()
    service = WorkbookGenerationService(settings, progress_reporter=reporter)

    result = service.generate(workbook_path=INVENTORY, output_path=output)

    assert result.labels_created >= 1
    assert [event.stage for event in reporter.events] == [
        GenerationStage.IMPORTING,
        GenerationStage.VALIDATING,
        GenerationStage.GENERATING_BARCODES,
        GenerationStage.CREATING_LABELS,
        GenerationStage.SAVING,
    ]
    assert [event.message for event in reporter.events] == [
        "Importing workbook...",
        "Validating books...",
        "Generating barcodes...",
        "Creating labels...",
        "Saving workbook...",
    ]


def test_progress_reporter_exceptions_do_not_abort_generation(
    tmp_path: Path,
) -> None:
    barcodes = tmp_path / "barcodes"
    barcodes.mkdir()
    output = tmp_path / "labels.xlsx"
    settings = load_application_settings(
        workbook_path=INVENTORY,
        barcode_output_directory=barcodes,
        label_template_id=DEFAULT_LABEL_TEMPLATE_ID,
        overwrite=True,
    )

    class BoomReporter:
        def on_progress(self, progress: GenerationProgress) -> None:
            raise RuntimeError("reporter boom")

    service = WorkbookGenerationService(settings, progress_reporter=BoomReporter())
    result = service.generate(workbook_path=INVENTORY, output_path=output)
    assert output.is_file()
    assert result.labels_created >= 1
