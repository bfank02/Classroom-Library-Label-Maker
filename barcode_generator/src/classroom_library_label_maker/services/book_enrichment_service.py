"""Book enrichment service — provider-agnostic metadata enrichment.

This module defines the orchestration layer for enriching :class:`Book`
records via pluggable :class:`BookEnrichmentProvider` implementations.

Phase 1 ships :class:`NullBookEnrichmentProvider`, which leaves books
unchanged and returns ``SKIPPED``. :class:`GoogleBooksEnrichmentProvider`
is available under ``services.lookups`` for explicit injection; it is not
the default and is not used by generation.

This service is **not** wired into :class:`WorkbookGenerationService` or the
GUI in this release — generation behavior remains identical to Version 1.0.
"""

from __future__ import annotations

from collections.abc import Sequence

from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.models import (
    Book,
    BookEnrichmentResult,
    BookEnrichmentStatus,
)
from classroom_library_label_maker.services.protocols import BookEnrichmentProvider

_logger = get_logger("book_enrichment_service")


class NullBookEnrichmentProvider:
    """No-op enrichment provider that preserves Version 1.0 behavior.

    Always returns :attr:`BookEnrichmentStatus.SKIPPED` without modifying the
    book or performing network I/O. Use as the default collaborator until a
    real catalog provider is configured.
    """

    def enrich(self, book: Book) -> BookEnrichmentResult:
        """Return a skipped enrichment result for ``book``.

        Args:
            book: Book that would have been enriched.

        Returns:
            Result with ``SKIPPED`` status and the book's ISBN.
        """
        return BookEnrichmentResult(
            isbn=book.isbn,
            status=BookEnrichmentStatus.SKIPPED,
            title=book.title,
            author=book.author,
            message="Enrichment skipped (null provider)",
        )


class BookEnrichmentService:
    """Delegate book enrichment to a :class:`BookEnrichmentProvider`.

    Responsibilities are limited to:

    * Holding a provider collaborator (defaults to the null provider)
    * Forwarding single-book and batch enrichment requests
    * Remaining free of HTTP, catalog, or GUI concerns

    The service depends only on the provider protocol — concrete backends
    must not leak into this module.
    """

    def __init__(
        self,
        *,
        provider: BookEnrichmentProvider | None = None,
    ) -> None:
        """Initialize the service.

        Args:
            provider: Enrichment backend. Defaults to
                :class:`NullBookEnrichmentProvider`.
        """
        self._provider: BookEnrichmentProvider = (
            provider if provider is not None else NullBookEnrichmentProvider()
        )

    @property
    def provider(self) -> BookEnrichmentProvider:
        """Return the configured enrichment provider."""
        return self._provider

    def enrich(self, book: Book) -> BookEnrichmentResult:
        """Enrich a single book via the configured provider.

        Args:
            book: Book to enrich.

        Returns:
            Provider-produced :class:`BookEnrichmentResult`.
        """
        result = self._provider.enrich(book)
        _logger.debug(
            "Enrichment %s for isbn=%s status=%s",
            type(self._provider).__name__,
            book.isbn,
            result.status.value,
        )
        return result

    def enrich_many(self, books: Sequence[Book]) -> list[BookEnrichmentResult]:
        """Enrich each book in order, preserving input sequence.

        Args:
            books: Books to enrich (may be empty).

        Returns:
            One :class:`BookEnrichmentResult` per input book, in the same order.
        """
        return [self.enrich(book) for book in books]
