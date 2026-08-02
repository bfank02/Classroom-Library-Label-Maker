"""Background workbook generation worker (Qt thread, no UI).

Runs :class:`WorkbookGenerationService` off the GUI thread. Forwards engine
progress and emits completion or failure — never touches widgets. The service
itself remains Qt-unaware.

Supports prepare → (GUI review) → produce so barcodes/labels use the same
authoritative post-review book collection as inventory updates.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QObject, Signal, Slot

from classroom_library_label_maker.models import (
    ApplicationSettings,
    Book,
    EnrichmentSummary,
    WorkbookGenerationResult,
    WorkbookGenerationWarning,
)
from classroom_library_label_maker.progress import (
    GenerationProgress,
    GenerationProgressReporter,
)
from classroom_library_label_maker.services.workbook_generation_service import (
    PreparedGeneration,
    WorkbookGenerationService,
)


class GenerationPhase(StrEnum):
    """Which portion of generation the worker should run."""

    PREPARE = "prepare"
    PRODUCE = "produce"
    FULL = "full"


class WorkbookGenerator(Protocol):
    """Minimal generation engine protocol used by the worker."""

    def generate(
        self,
        *,
        workbook_path: Path | None = None,
        output_path: Path | None = None,
        progress_reporter: GenerationProgressReporter | None = None,
    ) -> WorkbookGenerationResult:
        """Run full generation and return a result."""
        ...


class PhasedWorkbookGenerator(WorkbookGenerator, Protocol):
    """Generator that supports prepare/produce around interactive review."""

    def prepare(
        self,
        *,
        workbook_path: Path | None = None,
        progress_reporter: GenerationProgressReporter | None = None,
    ) -> PreparedGeneration:
        """Import and enrich without writing labels."""
        ...

    def produce(
        self,
        books: Sequence[Book],
        *,
        source_rows: Sequence[int],
        enrichment: EnrichmentSummary | None = None,
        prior_warnings: Sequence[WorkbookGenerationWarning] = (),
        books_imported: int | None = None,
        output_path: Path | None = None,
        progress_reporter: GenerationProgressReporter | None = None,
        started_at: float | None = None,
    ) -> WorkbookGenerationResult:
        """Generate barcodes/labels from an authoritative book list."""
        ...


GenerationServiceFactory = Callable[[ApplicationSettings], WorkbookGenerator]


@dataclass(frozen=True, slots=True)
class GenerationJob:
    """Immutable inputs for one background generation phase."""

    settings: ApplicationSettings
    workbook_path: Path
    output_path: Path
    phase: GenerationPhase = GenerationPhase.FULL
    books: tuple[Book, ...] | None = None
    source_rows: tuple[int, ...] | None = None
    enrichment: EnrichmentSummary | None = None
    prior_warnings: tuple[WorkbookGenerationWarning, ...] = ()
    books_imported: int = 0
    started_at: float | None = None


class _SignalProgressReporter:
    """Adapters engine progress into a Qt signal (no widgets)."""

    def __init__(self, emit_progress: Callable[[GenerationProgress], None]) -> None:
        self._emit_progress = emit_progress

    def on_progress(self, progress: GenerationProgress) -> None:
        self._emit_progress(progress)


def _default_generation_service(settings: ApplicationSettings) -> WorkbookGenerator:
    return WorkbookGenerationService(settings)


def _supports_phases(service: object) -> bool:
    return callable(getattr(service, "prepare", None)) and callable(
        getattr(service, "produce", None)
    )


class GenerationWorker(QObject):
    """Execute one :class:`GenerationJob` on the worker thread.

    Signals
    -------
    progress:
        Emitted with a :class:`GenerationProgress` for each engine stage.
    prepared:
        Emitted with a :class:`PreparedGeneration` after the prepare phase.
    completed:
        Emitted with a :class:`WorkbookGenerationResult` on produce/full success.
    failed:
        Emitted with the caught exception instance on failure.
    """

    progress = Signal(object)
    prepared = Signal(object)
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
        """Run the requested generation phase and emit the outcome."""
        job = self._job
        reporter = _SignalProgressReporter(self.progress.emit)
        try:
            service = self._service_factory(job.settings)
            if job.phase is GenerationPhase.PREPARE:
                if not _supports_phases(service):
                    raise TypeError(
                        "generation service does not support prepare/produce"
                    )
                prepared = service.prepare(  # type: ignore[attr-defined]
                    workbook_path=job.workbook_path,
                    progress_reporter=reporter,
                )
                self.prepared.emit(prepared)
                return

            if job.phase is GenerationPhase.PRODUCE:
                if not _supports_phases(service):
                    raise TypeError(
                        "generation service does not support prepare/produce"
                    )
                if job.books is None or job.source_rows is None:
                    raise ValueError("produce phase requires books and source_rows")
                result = service.produce(  # type: ignore[attr-defined]
                    job.books,
                    source_rows=job.source_rows,
                    enrichment=job.enrichment,
                    prior_warnings=job.prior_warnings,
                    books_imported=job.books_imported,
                    output_path=job.output_path,
                    progress_reporter=reporter,
                    started_at=job.started_at,
                )
                self.completed.emit(result)
                return

            result = service.generate(
                workbook_path=job.workbook_path,
                output_path=job.output_path,
                progress_reporter=reporter,
            )
        except Exception as exc:
            self.failed.emit(exc)
            return
        self.completed.emit(result)
