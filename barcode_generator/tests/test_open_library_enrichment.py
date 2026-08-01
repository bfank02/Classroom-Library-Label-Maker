"""Tests for Open Library enrichment provider (mocked HTTP; no network)."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

from classroom_library_label_maker.models import (
    Book,
    BookEnrichmentResult,
    BookEnrichmentStatus,
)
from classroom_library_label_maker.services.book_enrichment_service import (
    BookEnrichmentService,
    create_default_enrichment_service,
)
from classroom_library_label_maker.services.lookups.composite import (
    CompositeBookEnrichmentProvider,
)
from classroom_library_label_maker.services.lookups.open_library import (
    OpenLibraryEnrichmentProvider,
)


def _book(
    *,
    title: str = "Hatchet",
    author: str = "Gary Paulsen",
) -> Book:
    return Book(isbn="MISSING", title=title, author=author, copies=1)


def _doc(
    *,
    key: str,
    title: str,
    authors: list[str],
    isbns: list[str] | None = None,
    publisher: list[str] | None = None,
    year: int | None = 1987,
) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "key": key,
        "title": title,
        "author_name": authors,
    }
    if isbns is not None:
        doc["isbn"] = isbns
    if publisher is not None:
        doc["publisher"] = publisher
    if year is not None:
        doc["first_publish_year"] = year
    return doc


def _payload(*docs: dict[str, Any]) -> dict[str, Any]:
    return {"numFound": len(docs), "docs": list(docs)}


class _ScriptedFetcher:
    def __init__(self, responses: list[dict[str, Any] | BaseException]) -> None:
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


def _query_params(url: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(url).query)


class _StubProvider:
    def __init__(
        self,
        *,
        name: str,
        result: BookEnrichmentResult,
        calls: list[str] | None = None,
    ) -> None:
        self.provider_name = name
        self._result = result
        self._calls = calls if calls is not None else []

    def enrich(self, book: Book) -> BookEnrichmentResult:
        self._calls.append(self.provider_name)
        return self._result


def test_successful_open_library_lookup() -> None:
    fetcher = _ScriptedFetcher(
        [
            _payload(
                _doc(
                    key="/works/OL1W",
                    title="Hatchet",
                    authors=["Gary Paulsen"],
                    isbns=["9781416936473", "1416936475"],
                    publisher=["Simon & Schuster"],
                )
            )
        ]
    )
    result = OpenLibraryEnrichmentProvider(fetch_json=fetcher).enrich(_book())
    assert result.status is BookEnrichmentStatus.FOUND
    assert result.isbn == "9781416936473"
    assert result.provider_name == "Open Library"
    assert result.metadata["isbn13"] == "9781416936473"
    assert result.metadata["provider"] == "open_library"
    params = _query_params(fetcher.urls[0])
    assert params["title"] == ["Hatchet"]
    assert params["author"] == ["Gary Paulsen"]


def test_title_only_fallback() -> None:
    fetcher = _ScriptedFetcher(
        [
            _payload(),  # title+author miss
            _payload(
                _doc(
                    key="/works/OL2W",
                    title="Hatchet",
                    authors=["Gary Paulsen"],
                    isbns=["9781416936473"],
                )
            ),
        ]
    )
    result = OpenLibraryEnrichmentProvider(fetch_json=fetcher).enrich(_book())
    assert result.status is BookEnrichmentStatus.FOUND
    assert len(fetcher.urls) == 2
    assert "author" not in _query_params(fetcher.urls[1])
    assert _query_params(fetcher.urls[1])["title"] == ["Hatchet"]


def test_isbn13_preferred_over_isbn10() -> None:
    fetcher = _ScriptedFetcher(
        [
            _payload(
                _doc(
                    key="/works/OL3W",
                    title="Hatchet",
                    authors=["Gary Paulsen"],
                    isbns=["1416936475", "9781416936473"],
                )
            )
        ]
    )
    result = OpenLibraryEnrichmentProvider(fetch_json=fetcher).enrich(_book())
    assert result.status is BookEnrichmentStatus.FOUND
    assert result.isbn == "9781416936473"
    assert result.metadata["isbn13"] == "9781416936473"
    assert result.metadata["isbn10"] == "1416936475"


def test_isbn10_fallback_when_no_isbn13() -> None:
    fetcher = _ScriptedFetcher(
        [
            _payload(
                _doc(
                    key="/works/OL4W",
                    title="Hatchet",
                    authors=["Gary Paulsen"],
                    isbns=["1416936475"],
                )
            )
        ]
    )
    result = OpenLibraryEnrichmentProvider(fetch_json=fetcher).enrich(_book())
    assert result.status is BookEnrichmentStatus.FOUND
    assert result.isbn == "1416936475"
    assert result.metadata["isbn13"] is None
    assert result.metadata["isbn10"] == "1416936475"


def test_ambiguous_matches() -> None:
    fetcher = _ScriptedFetcher(
        [
            _payload(
                _doc(
                    key="/works/A",
                    title="Ocean Adventure",
                    authors=["Pat Lee"],
                    isbns=["9781111111111"],
                ),
                _doc(
                    key="/works/B",
                    title="Desert Adventure",
                    authors=["Pat Lee"],
                    isbns=["9782222222222"],
                ),
            )
        ]
    )
    book = Book(
        isbn="MISSING",
        title="Adventure",
        author="Pat Lee",
        copies=1,
    )
    result = OpenLibraryEnrichmentProvider(fetch_json=fetcher).enrich(book)
    assert result.status is BookEnrichmentStatus.AMBIGUOUS
    assert len(result.candidates) == 2
    assert result.provider_name == "Open Library"


def test_not_found_for_weak_matches() -> None:
    fetcher = _ScriptedFetcher(
        [
            _payload(
                _doc(
                    key="/works/X",
                    title="Completely Unrelated",
                    authors=["Someone Else"],
                    isbns=["9789999999999"],
                )
            ),
            _payload(),
        ]
    )
    result = OpenLibraryEnrichmentProvider(fetch_json=fetcher).enrich(_book())
    assert result.status is BookEnrichmentStatus.NOT_FOUND
    assert result.provider_name == "Open Library"


def test_composite_calls_open_library_after_google_not_found() -> None:
    calls: list[str] = []
    google = _StubProvider(
        name="Google Books",
        result=BookEnrichmentResult(
            isbn="MISSING",
            status=BookEnrichmentStatus.NOT_FOUND,
            message="miss",
            provider_name="Google Books",
        ),
        calls=calls,
    )
    open_library = _StubProvider(
        name="Open Library",
        result=BookEnrichmentResult(
            isbn="9781416936473",
            status=BookEnrichmentStatus.FOUND,
            title="Hatchet",
            provider_name="Open Library",
        ),
        calls=calls,
    )
    result = CompositeBookEnrichmentProvider((google, open_library)).enrich(_book())
    assert result.status is BookEnrichmentStatus.FOUND
    assert result.provider_name == "Open Library"
    assert calls == ["Google Books", "Open Library"]


def test_google_found_prevents_open_library() -> None:
    calls: list[str] = []
    google = _StubProvider(
        name="Google Books",
        result=BookEnrichmentResult(
            isbn="9780064400558",
            status=BookEnrichmentStatus.FOUND,
            provider_name="Google Books",
        ),
        calls=calls,
    )
    open_library = _StubProvider(
        name="Open Library",
        result=BookEnrichmentResult(
            isbn="9781416936473",
            status=BookEnrichmentStatus.FOUND,
            provider_name="Open Library",
        ),
        calls=calls,
    )
    result = CompositeBookEnrichmentProvider((google, open_library)).enrich(_book())
    assert result.status is BookEnrichmentStatus.FOUND
    assert result.provider_name == "Google Books"
    assert calls == ["Google Books"]


def test_google_ambiguous_prevents_open_library() -> None:
    calls: list[str] = []
    google = _StubProvider(
        name="Google Books",
        result=BookEnrichmentResult(
            isbn="MISSING",
            status=BookEnrichmentStatus.AMBIGUOUS,
            provider_name="Google Books",
        ),
        calls=calls,
    )
    open_library = _StubProvider(
        name="Open Library",
        result=BookEnrichmentResult(
            isbn="9781416936473",
            status=BookEnrichmentStatus.FOUND,
            provider_name="Open Library",
        ),
        calls=calls,
    )
    result = CompositeBookEnrichmentProvider((google, open_library)).enrich(_book())
    assert result.status is BookEnrichmentStatus.AMBIGUOUS
    assert result.provider_name == "Google Books"
    assert calls == ["Google Books"]


def test_provider_attribution_on_result() -> None:
    fetcher = _ScriptedFetcher(
        [
            _payload(
                _doc(
                    key="/works/OL1W",
                    title="Hatchet",
                    authors=["Gary Paulsen"],
                    isbns=["9781416936473"],
                )
            )
        ]
    )
    result = OpenLibraryEnrichmentProvider(fetch_json=fetcher).enrich(_book())
    as_dict = result.to_dict()
    assert as_dict["provider_name"] == "Open Library"


def test_cache_prevents_duplicate_provider_calls() -> None:
    calls: list[str] = []
    google = _StubProvider(
        name="Google Books",
        result=BookEnrichmentResult(
            isbn="MISSING",
            status=BookEnrichmentStatus.NOT_FOUND,
            provider_name="Google Books",
        ),
        calls=calls,
    )
    open_library = _StubProvider(
        name="Open Library",
        result=BookEnrichmentResult(
            isbn="9781416936473",
            status=BookEnrichmentStatus.FOUND,
            provider_name="Open Library",
        ),
        calls=calls,
    )
    service = BookEnrichmentService(
        provider=CompositeBookEnrichmentProvider((google, open_library))
    )
    book = _book()
    assert service.enrich(book).provider_name == "Open Library"
    assert service.enrich(book).provider_name == "Open Library"
    assert calls == ["Google Books", "Open Library"]
    assert service.cache_hits == 1


def test_create_default_includes_open_library_second() -> None:
    service = create_default_enrichment_service(api_key=None)
    provider = service.provider
    assert isinstance(provider, CompositeBookEnrichmentProvider)
    assert len(provider.providers) == 2
    assert provider.providers[0].provider_name == "Google Books"
    assert provider.providers[1].provider_name == "Open Library"


def test_rejects_invalid_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        OpenLibraryEnrichmentProvider(timeout_seconds=0)
