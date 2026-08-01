"""Protocols for optional enrichment, progress reporting, and cancellation.

Book enrichment uses :class:`BookEnrichmentProvider` (Book →
:class:`~classroom_library_label_maker.models.BookEnrichmentResult`). Catalog
implementations will live under ``services.lookups`` when those features are
built. Cover downloads use :class:`CoverDownloadService` under
``services.covers``. Progress reporters and cancellation tokens may be
supplied by CLI or future UI layers without changing
:class:`BatchProcessingService` method signatures.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from classroom_library_label_maker.models import (
    Book,
    BookEnrichmentResult,
    BookProcessingResult,
    CoverImageResult,
    IsbnLookupResult,
)


class BookEnrichmentProvider(Protocol):
    """Provider-agnostic contract for enriching a :class:`Book`.

    Implementations must not expose HTTP, API keys, or catalog-specific types
    through this interface. Return a :class:`BookEnrichmentResult` that
    describes the outcome (found, not found, skipped, ambiguous, or error).

    Future Google Books / Open Library adapters implement this protocol and
    are injected into
    :class:`~classroom_library_label_maker.services.book_enrichment_service.BookEnrichmentService`.
    """

    def enrich(self, book: Book) -> BookEnrichmentResult:
        """Enrich ``book`` with catalog metadata when available.

        Args:
            book: Book to enrich (ISBN and existing fields).

        Returns:
            Immutable enrichment outcome. Does not mutate ``book``.
        """
        ...


class IsbnLookupService(Protocol):
    """Protocol for future ISBN-string metadata lookup providers.

    Narrower than :class:`BookEnrichmentProvider`: operates on an ISBN string
    rather than a :class:`Book`. Prefer ``BookEnrichmentProvider`` for new
    enrichment pipelines; this protocol remains for low-level ISBN lookups.
    """

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


class BatchCancellationToken(Protocol):
    """Extension point for cooperative batch cancellation.

    Future UI layers can supply a token so the operator can stop a long batch
    between books. :class:`BatchProcessingService` accepts an optional token
    today so the constructor API stays stable when enforcement is added.

    **Not enforced in this release.** Passing a token has no effect until a
    future sprint checks ``is_cancellation_requested`` between books and stops
    gracefully (partial results retained).
    """

    def is_cancellation_requested(self) -> bool:
        """Return True when the caller has requested that the batch stop."""
        ...
