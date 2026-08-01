"""Book enrichment service — provider-agnostic metadata enrichment.

This module defines the orchestration layer for enriching :class:`Book`
records via pluggable :class:`BookEnrichmentProvider` implementations.

Phase 1 ships :class:`NullBookEnrichmentProvider`, which leaves books
unchanged and returns ``SKIPPED``. Production generation injects a
:class:`~classroom_library_label_maker.services.lookups.composite.CompositeBookEnrichmentProvider`
(currently wrapping Google Books only) via
:func:`create_default_enrichment_service`.

An in-memory result cache lives on this service (not on providers) so
duplicate title/author lookups within a single run share one provider call.
The cache is discarded when the service instance is destroyed.

This service is wired into :class:`WorkbookGenerationService` when
``lookup_missing_isbns`` is enabled. Catalog providers remain injectable;
the default production provider is the composite pipeline via
:func:`create_default_enrichment_service`.
"""

from __future__ import annotations

from collections.abc import Sequence

from classroom_library_label_maker.constants import MISSING_ISBN_PLACEHOLDER
from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.models import (
    Book,
    BookEnrichmentResult,
    BookEnrichmentStatus,
)
from classroom_library_label_maker.services.enrichment_normalize import (
    normalize_catalog_text,
)
from classroom_library_label_maker.services.protocols import BookEnrichmentProvider

_logger = get_logger("book_enrichment_service")


def book_needs_isbn_lookup(book: Book) -> bool:
    """Return True when ``book`` is missing an ISBN and should be enriched."""
    raw = str(book.isbn).strip()
    if not raw:
        return True
    return raw.casefold() == MISSING_ISBN_PLACEHOLDER.casefold()


def enrichment_cache_key(book: Book) -> tuple[str, str]:
    """Return the deterministic in-memory cache key for ``book``.

    Key components are normalized title and author only (ISBN is excluded so
    inventory rows missing ISBNs still share lookups for the same work).
    """
    return (
        normalize_catalog_text(book.title),
        normalize_catalog_text(book.author),
    )


def create_default_enrichment_service(
    *,
    api_key: str | None = None,
) -> BookEnrichmentService:
    """Build the production enrichment service (composite provider pipeline).

    Imported lazily so :class:`WorkbookGenerationService` can depend on
    :class:`BookEnrichmentService` without referencing catalog adapters.

    Phase 5.2 ships Google Books alone inside
    :class:`~classroom_library_label_maker.services.lookups.composite.CompositeBookEnrichmentProvider`
    so additional catalog providers can be appended later without changing
    the service or generation wiring.

    Args:
        api_key: Optional Google Books API key already resolved by application
            configuration. The provider does not read the environment; pass
            ``None`` for anonymous mode.
    """
    from classroom_library_label_maker.services.lookups.composite import (
        CompositeBookEnrichmentProvider,
    )
    from classroom_library_label_maker.services.lookups.google_books import (
        GoogleBooksEnrichmentProvider,
    )

    return BookEnrichmentService(
        provider=CompositeBookEnrichmentProvider(
            (GoogleBooksEnrichmentProvider(api_key=api_key),)
        ),
    )


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
    * Caching enrichment results in memory for the lifetime of this instance
    * Forwarding single-book and batch enrichment requests on cache miss
    * Remaining free of HTTP, catalog, or GUI concerns

    The service depends only on the provider protocol — concrete backends
    must not leak into this module. Caching belongs here so every provider
    benefits without duplicating cache logic.
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
        self._cache: dict[tuple[str, str], BookEnrichmentResult] = {}
        self._cache_hits = 0
        self._cache_misses = 0

    @property
    def provider(self) -> BookEnrichmentProvider:
        """Return the configured enrichment provider."""
        return self._provider

    @property
    def cache_hits(self) -> int:
        """Number of enrichments served from the in-memory cache."""
        return self._cache_hits

    @property
    def cache_misses(self) -> int:
        """Number of enrichments that invoked the provider."""
        return self._cache_misses

    @property
    def cache_size(self) -> int:
        """Number of distinct title/author keys currently cached."""
        return len(self._cache)

    def enrich(self, book: Book) -> BookEnrichmentResult:
        """Enrich a single book via the configured provider.

        Returns a cached :class:`BookEnrichmentResult` when a prior call used
        the same normalized title and author. Does not mutate ``book``.

        Args:
            book: Book to enrich.

        Returns:
            Cached or provider-produced :class:`BookEnrichmentResult`.
        """
        key = enrichment_cache_key(book)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache_hits += 1
            _logger.debug(
                "Enrichment cache hit for title=%r author=%r status=%s",
                book.title,
                book.author,
                cached.status.value,
            )
            return cached

        self._cache_misses += 1
        result = self._provider.enrich(book)
        # Do not cache transient rate limits — a later retry in the same run
        # (or a duplicate title after cooldown) should hit the provider again.
        if not (
            result.status is BookEnrichmentStatus.ERROR
            and isinstance(result.metadata, dict)
            and result.metadata.get("error_kind") == "rate_limit"
        ):
            self._cache[key] = result
        _logger.debug(
            "Enrichment %s for isbn=%s status=%s (cache miss)",
            type(self._provider).__name__,
            book.isbn,
            result.status.value,
        )
        return result

    def enrich_many(self, books: Sequence[Book]) -> list[BookEnrichmentResult]:
        """Enrich each book in order, preserving input sequence.

        Uses the same in-memory cache as :meth:`enrich`.

        Args:
            books: Books to enrich (may be empty).

        Returns:
            One :class:`BookEnrichmentResult` per input book, in the same order.
        """
        return [self.enrich(book) for book in books]
