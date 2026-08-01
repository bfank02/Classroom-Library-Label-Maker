"""Tests for Google Books enrichment provider (mocked HTTP; no network)."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

from classroom_library_label_maker.models import (
    Book,
    BookEnrichmentStatus,
)
from classroom_library_label_maker.services.lookups.google_books import (
    GoogleBooksEnrichmentProvider,
    GoogleBooksTransportError,
    author_similarity,
    normalize_catalog_text,
    title_similarity,
)


def _book(
    *,
    isbn: str = "9780064400558",
    title: str = "Charlotte's Web",
    author: str = "E. B. White",
) -> Book:
    return Book(isbn=isbn, title=title, author=author, copies=1)


def _volume(
    *,
    volume_id: str,
    title: str,
    authors: list[str],
    isbn13: str | None = None,
    isbn10: str | None = None,
    publisher: str | None = "HarperCollins",
) -> dict[str, Any]:
    identifiers: list[dict[str, str]] = []
    if isbn13:
        identifiers.append({"type": "ISBN_13", "identifier": isbn13})
    if isbn10:
        identifiers.append({"type": "ISBN_10", "identifier": isbn10})
    volume_info: dict[str, Any] = {
        "title": title,
        "authors": authors,
    }
    if identifiers:
        volume_info["industryIdentifiers"] = identifiers
    if publisher:
        volume_info["publisher"] = publisher
        volume_info["publishedDate"] = "1952"
    return {"id": volume_id, "volumeInfo": volume_info}


def _payload(*volumes: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "books#volumes", "totalItems": len(volumes), "items": list(volumes)}


def _query_from_url(url: str) -> str:
    return parse_qs(urlparse(url).query).get("q", [""])[0]


class _ScriptedFetcher:
    """Return canned payloads (or errors) keyed by ordered call index."""

    def __init__(
        self,
        responses: list[dict[str, Any] | BaseException],
    ) -> None:
        self.responses = list(responses)
        self.urls: list[str] = []

    def __call__(self, url: str) -> dict[str, Any]:
        self.urls.append(url)
        if not self.responses:
            raise AssertionError(f"Unexpected fetch: {url}")
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


# --- Normalization / scoring helpers -----------------------------------------


def test_normalize_ignores_case_punctuation_and_whitespace() -> None:
    assert normalize_catalog_text("  Charlotte's   Web! ") == "charlottes web"
    assert normalize_catalog_text("E. B. White") == "e b white"
    assert normalize_catalog_text("Charlotte's Web") == normalize_catalog_text(
        "charlottes web!!"
    )


def test_title_and_author_similarity_high_for_near_matches() -> None:
    assert title_similarity("Charlotte's Web", "Charlotte's Web") >= 0.99
    assert author_similarity("E. B. White", ["E. B. White"]) >= 0.99
    assert author_similarity("White", ["E. B. White"]) >= 0.9


# --- Exact / title-only / ambiguous / not found ------------------------------


def test_exact_match_title_and_author() -> None:
    """intitle+inauthor hit with strong scores should return FOUND."""
    fetcher = _ScriptedFetcher(
        [
            _payload(
                _volume(
                    volume_id="vol1",
                    title="Charlotte's Web",
                    authors=["E. B. White"],
                    isbn13="9780064400558",
                    isbn10="0064400557",
                )
            )
        ]
    )
    provider = GoogleBooksEnrichmentProvider(fetch_json=fetcher)
    book = _book()
    result = provider.enrich(book)

    assert result.status is BookEnrichmentStatus.FOUND
    assert result.candidates == ()
    assert result.isbn == "9780064400558"
    assert result.title == "Charlotte's Web"
    assert result.author == "E. B. White"
    assert result.metadata["isbn13"] == "9780064400558"
    assert result.metadata["isbn10"] == "0064400557"
    assert result.metadata["provider"] == "google_books"
    assert result.metadata["normalized_title"] == "charlottes web"
    assert book.title == "Charlotte's Web"  # original unchanged
    assert "intitle:" in _query_from_url(fetcher.urls[0])
    assert "inauthor:" in _query_from_url(fetcher.urls[0])


def test_title_only_match_after_empty_combined_query() -> None:
    """Fall through to intitle-only when the first query returns nothing."""
    fetcher = _ScriptedFetcher(
        [
            _payload(),  # intitle+inauthor empty
            _payload(
                _volume(
                    volume_id="vol2",
                    title="Charlotte's Web",
                    authors=["E. B. White"],
                    isbn13="9780064400558",
                )
            ),
        ]
    )
    result = GoogleBooksEnrichmentProvider(fetch_json=fetcher).enrich(_book())

    assert result.status is BookEnrichmentStatus.FOUND
    assert len(fetcher.urls) == 2
    assert "inauthor:" not in _query_from_url(fetcher.urls[1])
    assert _query_from_url(fetcher.urls[1]).startswith("intitle:")


def test_ambiguous_when_two_distinct_confident_matches() -> None:
    """Peers above FOUND that are not editions → AMBIGUOUS."""
    volumes = _payload(
        _volume(
            volume_id="a",
            title="Ocean Adventure",
            authors=["Pat Lee"],
            isbn13="9781111111111",
        ),
        _volume(
            volume_id="b",
            title="Desert Adventure",
            authors=["Pat Lee"],
            isbn13="9782222222222",
        ),
    )
    book = Book(
        isbn="9780000000000",
        title="Adventure",
        author="Pat Lee",
        copies=1,
    )
    result = GoogleBooksEnrichmentProvider(
        fetch_json=_ScriptedFetcher([volumes])
    ).enrich(book)
    assert result.status is BookEnrichmentStatus.AMBIGUOUS
    assert "multiple" in result.message.lower()
    assert result.metadata.get("isbn13") in {"9781111111111", "9782222222222"}
    assert len(result.candidates) == 2
    confidences = [c.confidence_score for c in result.candidates]
    assert confidences == sorted(confidences, reverse=True)
    assert {c.isbn13 for c in result.candidates} == {
        "9781111111111",
        "9782222222222",
    }


def test_no_match_across_all_queries() -> None:
    fetcher = _ScriptedFetcher([_payload(), _payload(), _payload()])
    result = GoogleBooksEnrichmentProvider(fetch_json=fetcher).enrich(_book())

    assert result.status is BookEnrichmentStatus.NOT_FOUND
    assert len(fetcher.urls) == 3
    queries = [_query_from_url(url) for url in fetcher.urls]
    assert "inauthor:" in queries[0]
    assert queries[1].startswith("intitle:")
    assert "inauthor:" not in queries[1]
    assert "Charlotte" in queries[2] and "White" in queries[2]


def test_weak_results_are_not_found() -> None:
    fetcher = _ScriptedFetcher(
        [
            _payload(
                _volume(
                    volume_id="x",
                    title="Completely Unrelated Book",
                    authors=["Someone Else"],
                    isbn13="9789999999999",
                )
            ),
            _payload(),
            _payload(),
        ]
    )
    result = GoogleBooksEnrichmentProvider(fetch_json=fetcher).enrich(_book())
    assert result.status is BookEnrichmentStatus.NOT_FOUND


# --- Multiple editions -------------------------------------------------------


def test_multiple_editions_resolve_to_found() -> None:
    """Same work, different ISBNs → FOUND preferring ISBN-13."""
    fetcher = _ScriptedFetcher(
        [
            _payload(
                _volume(
                    volume_id="ed1",
                    title="Charlotte's Web",
                    authors=["E. B. White"],
                    isbn10="0064400557",
                ),
                _volume(
                    volume_id="ed2",
                    title="Charlotte's Web",
                    authors=["E. B. White"],
                    isbn13="9780064400558",
                    isbn10="0064400557",
                ),
            )
        ]
    )
    result = GoogleBooksEnrichmentProvider(fetch_json=fetcher).enrich(_book())

    assert result.status is BookEnrichmentStatus.FOUND
    assert result.isbn == "9780064400558"
    assert result.metadata["isbn13"] == "9780064400558"
    assert "edition" in result.message.lower()


# --- Errors ------------------------------------------------------------------


def test_timeout_becomes_error() -> None:
    fetcher = _ScriptedFetcher(
        [GoogleBooksTransportError("Google Books request timed out", kind="timeout")]
    )
    result = GoogleBooksEnrichmentProvider(fetch_json=fetcher).enrich(_book())

    assert result.status is BookEnrichmentStatus.ERROR
    assert "timed out" in result.message.lower()
    assert result.metadata["error_kind"] == "timeout"


def test_timeout_error_from_timeout_exception() -> None:
    fetcher = _ScriptedFetcher([TimeoutError()])
    result = GoogleBooksEnrichmentProvider(fetch_json=fetcher).enrich(_book())
    assert result.status is BookEnrichmentStatus.ERROR
    assert result.metadata["error_kind"] == "timeout"


def test_malformed_response_becomes_error() -> None:
    fetcher = _ScriptedFetcher(
        [GoogleBooksTransportError("not valid JSON", kind="malformed")]
    )
    result = GoogleBooksEnrichmentProvider(fetch_json=fetcher).enrich(_book())
    assert result.status is BookEnrichmentStatus.ERROR
    assert result.metadata["error_kind"] == "malformed"


def test_malformed_items_type_becomes_error() -> None:
    fetcher = _ScriptedFetcher([{"items": "oops"}])
    result = GoogleBooksEnrichmentProvider(fetch_json=fetcher).enrich(_book())
    assert result.status is BookEnrichmentStatus.ERROR
    assert result.metadata["error_kind"] == "malformed"


def test_http_failure_becomes_error() -> None:
    fetcher = _ScriptedFetcher(
        [GoogleBooksTransportError("Google Books HTTP error: 503", kind="http")]
    )
    result = GoogleBooksEnrichmentProvider(fetch_json=fetcher).enrich(_book())
    assert result.status is BookEnrichmentStatus.ERROR
    assert result.metadata["error_kind"] == "http"


def test_does_not_mutate_book_on_found() -> None:
    book = _book(title="Charlotte's Web", author="E. B. White")
    original = book.to_dict()
    fetcher = _ScriptedFetcher(
        [
            _payload(
                _volume(
                    volume_id="v",
                    title="Charlotte's Web: Full Color Edition",
                    authors=["E. B. White"],
                    isbn13="9780064400558",
                )
            )
        ]
    )
    GoogleBooksEnrichmentProvider(fetch_json=fetcher).enrich(book)
    assert book.to_dict() == original


def test_free_text_query_used_third() -> None:
    """Third strategy is plain title+author when earlier queries miss."""
    fetcher = _ScriptedFetcher(
        [
            _payload(),
            _payload(),
            _payload(
                _volume(
                    volume_id="v",
                    title="Charlotte's Web",
                    authors=["E. B. White"],
                    isbn13="9780064400558",
                )
            ),
        ]
    )
    result = GoogleBooksEnrichmentProvider(fetch_json=fetcher).enrich(_book())
    assert result.status is BookEnrichmentStatus.FOUND
    assert len(fetcher.urls) == 3
    assert _query_from_url(fetcher.urls[2]) == "Charlotte's Web E. B. White"


def test_provider_rejects_invalid_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        GoogleBooksEnrichmentProvider(timeout_seconds=0)


def test_enrich_via_book_enrichment_service() -> None:
    """Provider plugs into BookEnrichmentService without generation wiring."""
    from classroom_library_label_maker.services import BookEnrichmentService

    fetcher = _ScriptedFetcher(
        [
            _payload(
                _volume(
                    volume_id="v",
                    title="Charlotte's Web",
                    authors=["E. B. White"],
                    isbn13="9780064400558",
                )
            )
        ]
    )
    service = BookEnrichmentService(
        provider=GoogleBooksEnrichmentProvider(fetch_json=fetcher)
    )
    result = service.enrich(_book())
    assert result.status is BookEnrichmentStatus.FOUND


def test_build_queries_never_author_only() -> None:
    from classroom_library_label_maker.services.lookups.google_books import (
        _build_queries,
    )

    queries = _build_queries("Title", "Author")
    assert all("intitle" in q or "Title" in q for q in queries)
    assert not any(q.strip().startswith("inauthor:") for q in queries)
    assert not any(q == 'inauthor:"Author"' for q in queries)
