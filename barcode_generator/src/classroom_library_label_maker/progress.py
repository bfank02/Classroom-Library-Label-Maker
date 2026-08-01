"""Qt-independent progress reporting for workbook generation.

Used by :class:`~classroom_library_label_maker.services.workbook_generation_service.WorkbookGenerationService`
and consumable by the desktop GUI, CLI, or other adapters without embedding
UI concerns in the engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class GenerationStage(StrEnum):
    """Significant milestones during workbook generation."""

    IMPORTING = "importing"
    ENRICHING = "enriching"
    VALIDATING = "validating"
    GENERATING_BARCODES = "generating_barcodes"
    CREATING_LABELS = "creating_labels"
    SAVING = "saving"


_STAGE_MESSAGES: dict[GenerationStage, str] = {
    GenerationStage.IMPORTING: "Importing workbook...",
    GenerationStage.ENRICHING: "Looking up missing ISBNs...",
    GenerationStage.VALIDATING: "Validating books...",
    GenerationStage.GENERATING_BARCODES: "Generating barcodes...",
    GenerationStage.CREATING_LABELS: "Creating labels...",
    GenerationStage.SAVING: "Saving workbook...",
}


@dataclass(frozen=True, slots=True)
class GenerationProgress:
    """Structured progress event from the generation engine.

    Attributes:
        stage: Machine-readable generation milestone.
        message: User-facing status text for this stage.
    """

    stage: GenerationStage
    message: str

    @classmethod
    def for_stage(cls, stage: GenerationStage) -> GenerationProgress:
        """Build a progress event with the canonical message for ``stage``."""
        return cls(stage=stage, message=_STAGE_MESSAGES[stage])


class GenerationProgressReporter(Protocol):
    """Receives structured generation progress updates.

    Implementations may drive a GUI status line, CLI output, or logging.
    Callers treat reporter failures as non-fatal (logged by the service).
    """

    def on_progress(self, progress: GenerationProgress) -> None:
        """Handle one progress event."""
        ...
