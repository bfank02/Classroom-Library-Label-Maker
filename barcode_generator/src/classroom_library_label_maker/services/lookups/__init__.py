"""ISBN / catalog metadata lookup providers.

Catalog adapters implement
:class:`~classroom_library_label_maker.services.protocols.BookEnrichmentProvider`
and are injected into
:class:`~classroom_library_label_maker.services.book_enrichment_service.BookEnrichmentService`.

Available providers:

* :class:`CompositeBookEnrichmentProvider` — sequential provider pipeline
* :class:`GoogleBooksEnrichmentProvider` — Google Books Volumes API (primary)
* :class:`OpenLibraryEnrichmentProvider` — Open Library Search API (fallback)

Production generation uses the composite pipeline (Google Books, then Open
Library) via :func:`create_default_enrichment_service`.
"""

from __future__ import annotations

from classroom_library_label_maker.services.lookups.composite import (
    CompositeBookEnrichmentProvider,
)
from classroom_library_label_maker.services.lookups.google_books import (
    GoogleBooksEnrichmentProvider,
)
from classroom_library_label_maker.services.lookups.open_library import (
    OpenLibraryEnrichmentProvider,
)

__all__ = [
    "CompositeBookEnrichmentProvider",
    "GoogleBooksEnrichmentProvider",
    "OpenLibraryEnrichmentProvider",
]
