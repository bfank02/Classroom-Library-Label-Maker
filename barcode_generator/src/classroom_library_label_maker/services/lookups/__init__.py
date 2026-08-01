"""ISBN / catalog metadata lookup providers.

Catalog adapters implement
:class:`~classroom_library_label_maker.services.protocols.BookEnrichmentProvider`
and are injected into
:class:`~classroom_library_label_maker.services.book_enrichment_service.BookEnrichmentService`.

Available providers:

* :class:`CompositeBookEnrichmentProvider` — sequential provider pipeline
* :class:`GoogleBooksEnrichmentProvider` — Google Books Volumes API (title/author
  search)

Production generation uses the composite pipeline (currently Google Books
only) via :func:`create_default_enrichment_service`.
"""

from __future__ import annotations

from classroom_library_label_maker.services.lookups.composite import (
    CompositeBookEnrichmentProvider,
)
from classroom_library_label_maker.services.lookups.google_books import (
    GoogleBooksEnrichmentProvider,
)

__all__ = [
    "CompositeBookEnrichmentProvider",
    "GoogleBooksEnrichmentProvider",
]
