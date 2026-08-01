"""Composite book enrichment provider — sequential provider pipeline.

Chains multiple :class:`BookEnrichmentProvider` implementations so callers
(including :class:`BookEnrichmentService`) see a single provider. Concrete
catalog backends stay unaware of each other; the composite only depends on
the protocol.
"""

from __future__ import annotations

from collections.abc import Sequence
import logging

from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.models import (
    Book,
    BookEnrichmentResult,
    BookEnrichmentStatus,
)
from classroom_library_label_maker.services.protocols import BookEnrichmentProvider

_logger = get_logger("composite_enrichment")

__all__ = [
    "CompositeBookEnrichmentProvider",
]


def _provider_label(provider: BookEnrichmentProvider) -> str:
    """Return a human-readable provider label without knowing concrete types.

    Prefer an optional ``provider_name`` attribute when present; otherwise use
    the class name. Never inspect credentials or request configuration.
    """
    name = getattr(provider, "provider_name", None)
    if isinstance(name, str) and name.strip():
        return name.strip()
    return type(provider).__name__


class CompositeBookEnrichmentProvider:
    """Evaluate enrichment providers in injection order until one resolves.

    Flow for each provider:

    * ``FOUND`` / ``AMBIGUOUS`` — return immediately
    * ``NOT_FOUND`` / ``ERROR`` / ``SKIPPED`` — continue to the next provider

    If every provider returns a non-resolving status, return ``NOT_FOUND``.
    Providers are never reordered and are never queried in parallel.
    """

    provider_name = "Composite"

    def __init__(self, providers: Sequence[BookEnrichmentProvider]) -> None:
        """Initialize with an ordered provider pipeline.

        Args:
            providers: Enrichment backends in priority order (first = highest).
                Must contain at least one provider.

        Raises:
            ValueError: When ``providers`` is empty.
        """
        ordered = tuple(providers)
        if not ordered:
            raise ValueError("providers must contain at least one provider")
        self._providers = ordered

    @property
    def providers(self) -> tuple[BookEnrichmentProvider, ...]:
        """Return the injected providers in priority order."""
        return self._providers

    def enrich(self, book: Book) -> BookEnrichmentResult:
        """Try each provider sequentially until FOUND or AMBIGUOUS.

        Does not mutate ``book``. Does not cache (caching stays on
        :class:`BookEnrichmentService`).
        """
        last_message = "No catalog provider returned a usable match"
        provider_count = len(self._providers)

        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(
                "Composite enrichment lookup\nBook:\n%s\n%s\nProviders: %s",
                book.title,
                book.author,
                provider_count,
            )

        for index, provider in enumerate(self._providers, start=1):
            label = _provider_label(provider)
            result = provider.enrich(book)
            status = result.status

            if status in (
                BookEnrichmentStatus.FOUND,
                BookEnrichmentStatus.AMBIGUOUS,
            ):
                if _logger.isEnabledFor(logging.DEBUG):
                    _logger.debug(
                        "Provider %s/%s\n%s\nResult:\n%s\nReturning.",
                        index,
                        provider_count,
                        label,
                        status.value,
                    )
                return result

            if _logger.isEnabledFor(logging.DEBUG):
                continuing = index < provider_count
                _logger.debug(
                    "Provider %s/%s\n%s\nResult:\n%s\n%s",
                    index,
                    provider_count,
                    label,
                    status.value,
                    "Continuing..." if continuing else "No further providers.",
                )

            if result.message:
                last_message = result.message

        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(
                "Composite final decision: %s (%s)",
                BookEnrichmentStatus.NOT_FOUND.value,
                last_message,
            )

        return BookEnrichmentResult(
            isbn=book.isbn,
            status=BookEnrichmentStatus.NOT_FOUND,
            message=last_message,
            metadata={"provider": "composite"},
        )
