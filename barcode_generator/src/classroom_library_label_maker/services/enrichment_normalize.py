"""Shared title/author normalization for enrichment matching and caching.

Used by
:class:`~classroom_library_label_maker.services.book_enrichment_service.BookEnrichmentService`
(cache keys) and catalog providers (candidate comparison) so equivalent
strings share one deterministic form.
"""

from __future__ import annotations

import re

_PUNCTUATION_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_catalog_text(value: str) -> str:
    """Normalize title/author text for comparison and cache keys.

    Lowercases (casefold), strips punctuation, and collapses whitespace.
    Apostrophes and other punctuation are removed so ``Charlotte's`` and
    ``Charlottes`` compare equally.
    """
    text = value.casefold().strip()
    text = _PUNCTUATION_RE.sub("", text)
    text = text.replace("_", " ")
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text
