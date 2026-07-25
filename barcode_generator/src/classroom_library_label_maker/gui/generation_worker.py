"""Background workbook generation worker (Qt thread, no UI).

Runs :class:`WorkbookGenerationService` off the GUI thread. Emits completion
or failure signals only — never touches widgets. The service itself remains
Qt-unaware.
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


def _default_generation_service(settings: ApplicationSettings) -> WorkbookGenerator:
    return WorkbookGenerationService(settings)


class GenerationWorker(QObject):
    """Execute one :class:`GenerationJob` on the worker thread.

    Signals
    -------
    completed:
        Emitted with a :class:`WorkbookGenerationResult` on success.
    failed:
        Emitted with the caught exception instance on failure.
    """

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
        try:
            service = self._service_factory(job.settings)
            result = service.generate(
                workbook_path=job.workbook_path,
                output_path=job.output_path,
            )
        except Exception as exc:
            self.failed.emit(exc)
            return
        self.completed.emit(result)
