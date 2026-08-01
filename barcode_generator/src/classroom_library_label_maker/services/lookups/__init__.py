"""ISBN / catalog metadata lookup providers.

Catalog adapters implement
:class:`~classroom_library_label_maker.services.protocols.BookEnrichmentProvider`
and are injected into
:class:`~classroom_library_label_maker.services.book_enrichment_service.BookEnrichmentService`.

Available providers:

* :class:`GoogleBooksEnrichmentProvider` — Google Books Volumes API (title/author
  search). Not wired into generation / CLI / GUI by default.

The default enrichment collaborator remains
:class:`~classroom_library_label_maker.services.book_enrichment_service.NullBookEnrichmentProvider`.
"""

from __future__ import annotations

from classroom_library_label_maker.services.lookups.google_books import (
    GoogleBooksEnrichmentProvider,
)

__all__ = [
    "GoogleBooksEnrichmentProvider",
]
