"""Protocols for optional enrichment and progress reporting.

Implementations will live under ``services.lookups`` and ``services.covers``
when those features are built. Progress reporters may be supplied by CLI or
future UI layers without changing :class:`BatchProcessingService`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from classroom_library_label_maker.models import (
    BookProcessingResult,
    CoverImageResult,
    IsbnLookupResult,
)


class IsbnLookupService(Protocol):
    """Protocol for future ISBN metadata lookup providers."""

    def lookup(self, isbn: str) -> IsbnLookupResult:
        """Look up metadata for an ISBN.

        Args:
            isbn: Normalized ISBN.

        Returns:
            Lookup result with any available metadata.
        """
        ...


class CoverDownloadService(Protocol):
    """Protocol for future cover image download providers."""

    def download(self, isbn: str, output_dir: Path) -> CoverImageResult:
        """Download a cover image for an ISBN.

        Args:
            isbn: Normalized ISBN.
            output_dir: Directory for cover image files.

        Returns:
            Result describing the downloaded (or failed) cover.
        """
        ...


class BatchProgressReporter(Protocol):
    """Optional progress hook for batch processing.

    Implementations can drive CLI progress bars or future UI without changing
    the batch processing service public API. All methods are best-effort;
    reporter exceptions are swallowed and logged by the service.
    """

    def on_batch_started(self, total: int) -> None:
        """Called once before the first book is processed."""
        ...

    def on_book_processed(
        self,
        index: int,
        total: int,
        result: BookProcessingResult,
    ) -> None:
        """Called after each book finishes (``index`` is 1-based)."""
        ...

    def on_batch_completed(self, total: int) -> None:
        """Called once after all books have been processed."""
        ...
