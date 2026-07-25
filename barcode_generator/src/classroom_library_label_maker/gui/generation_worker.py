"""Background workbook generation worker (Qt thread, no UI).

Runs :class:`WorkbookGenerationService` off the GUI thread. Forwards engine
progress and emits completion or failure — never touches widgets. The service
itself remains Qt-unaware.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QObject, Signal, Slot

from classroom_library_label_maker.models import (
    ApplicationSettings,
    WorkbookGenerationResult,
)
from classroom_library_label_maker.progress import (
    GenerationProgress,
    GenerationProgressReporter,
)
from classroom_library_label_maker.services.workbook_generation_service import (
    WorkbookGenerationService,
)


class WorkbookGenerator(Protocol):
    """Minimal generation engine protocol used by the worker."""

    def generate(
        self,
        *,
        workbook_path: Path | None = None,
        output_path: Path | None = None,
        progress_reporter: GenerationProgressReporter | None = None,
    ) -> WorkbookGenerationResult:
        """Run generation and return a result."""
        ...


GenerationServiceFactory = Callable[[ApplicationSettings], WorkbookGenerator]


@dataclass(frozen=True, slots=True)
class GenerationJob:
    """Immutable inputs for one background generation run."""

    settings: ApplicationSettings
    workbook_path: Path
    output_path: Path


class _SignalProgressReporter:
    """Adapters engine progress into a Qt signal (no widgets)."""

    def __init__(self, emit_progress: Callable[[GenerationProgress], None]) -> None:
        self._emit_progress = emit_progress

    def on_progress(self, progress: GenerationProgress) -> None:
        self._emit_progress(progress)


def _default_generation_service(settings: ApplicationSettings) -> WorkbookGenerator:
    return WorkbookGenerationService(settings)


class GenerationWorker(QObject):
    """Execute one :class:`GenerationJob` on the worker thread.

    Signals
    -------
    progress:
        Emitted with a :class:`GenerationProgress` for each engine stage.
    completed:
        Emitted with a :class:`WorkbookGenerationResult` on success.
    failed:
        Emitted with the caught exception instance on failure.
    """

    progress = Signal(object)
    completed = Signal(object)
    failed = Signal(object)

    def __init__(
        self,
        job: GenerationJob,
        *,
        service_factory: GenerationServiceFactory | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._job = job
        self._service_factory = service_factory or _default_generation_service

    @property
    def job(self) -> GenerationJob:
        """Return the immutable generation inputs."""
        return self._job

    @Slot()
    def run(self) -> None:
        """Run ``WorkbookGenerationService.generate`` and emit the outcome."""
        job = self._job
        reporter = _SignalProgressReporter(self.progress.emit)
        try:
            service = self._service_factory(job.settings)
            result = service.generate(
                workbook_path=job.workbook_path,
                output_path=job.output_path,
                progress_reporter=reporter,
            )
        except Exception as exc:
            self.failed.emit(exc)
            return
        self.completed.emit(result)
