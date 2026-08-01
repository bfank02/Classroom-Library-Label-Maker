"""Tests for book enrichment architecture (service, null provider, models)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from classroom_library_label_maker.models import (
    Book,
    BookEnrichmentResult,
    BookEnrichmentStatus,
)
from classroom_library_label_maker.services import (
    BookEnrichmentService,
    NullBookEnrichmentProvider,
)
from classroom_library_label_maker.services.protocols import BookEnrichmentProvider


def _sample_book() -> Book:
    return Book(
        isbn="9780064400558",
        title="Charlotte's Web",
        author="E. B. White",
        copies=1,
    )


class _StubFoundProvider:
    """Minimal structural provider used to verify protocol compatibility."""

    def enrich(self, book: Book) -> BookEnrichmentResult:
        return BookEnrichmentResult(
            isbn=book.isbn,
            status=BookEnrichmentStatus.FOUND,
            title="Resolved Title",
            author="Resolved Author",
            message="stub hit",
            metadata={"publisher": "Stub Press", "subjects": ["fiction"]},
        )


class _StubNotFoundProvider:
    def enrich(self, book: Book) -> BookEnrichmentResult:
        return BookEnrichmentResult(
            isbn=book.isbn,
            status=BookEnrichmentStatus.NOT_FOUND,
            message="no catalog match",
        )


# --- Immutable models --------------------------------------------------------


def test_enrichment_status_values() -> None:
    """Statuses should use stable lowercase string values."""
    assert BookEnrichmentStatus.FOUND == "found"
    assert BookEnrichmentStatus.NOT_FOUND == "not_found"
    assert BookEnrichmentStatus.SKIPPED == "skipped"
    assert BookEnrichmentStatus.AMBIGUOUS == "ambiguous"
    assert BookEnrichmentStatus.ERROR == "error"


def test_enrichment_result_is_immutable() -> None:
    """BookEnrichmentResult fields must not be assignable after construction."""
    result = BookEnrichmentResult(
        isbn="9780064400558",
        status=BookEnrichmentStatus.FOUND,
        title="A",
        author="B",
        message="ok",
        metadata={"year": 1952},
    )
    with pytest.raises(FrozenInstanceError):
        result.title = "Changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.status = BookEnrichmentStatus.ERROR  # type: ignore[misc]


def test_enrichment_result_metadata_extension() -> None:
    """Additional metadata keys should serialize without redesigning the model."""
    result = BookEnrichmentResult(
        isbn="9780064400558",
        status=BookEnrichmentStatus.FOUND,
        metadata={"publisher": "Harper", "page_count": 192},
    )
    payload = result.to_dict()
    assert payload["status"] == "found"
    assert payload["metadata"]["publisher"] == "Harper"
    assert payload["metadata"]["page_count"] == 192
    assert payload["title"] is None
    assert payload["author"] is None


def test_enrichment_result_to_dict_copies_metadata() -> None:
    """to_dict should return a shallow copy of metadata, not the live dict."""
    metadata: dict[str, Any] = {"k": "v"}
    result = BookEnrichmentResult(
        isbn="9780064400558",
        status=BookEnrichmentStatus.FOUND,
        metadata=metadata,
    )
    payload = result.to_dict()
    payload["metadata"]["k"] = "mutated"
    assert result.metadata["k"] == "v"


# --- Null provider -----------------------------------------------------------


def test_null_provider_returns_skipped() -> None:
    """Null provider should skip enrichment and echo existing book fields."""
    book = _sample_book()
    result = NullBookEnrichmentProvider().enrich(book)

    assert result.status is BookEnrichmentStatus.SKIPPED
    assert result.isbn == book.isbn
    assert result.title == book.title
    assert result.author == book.author
    assert "null provider" in result.message.lower()
    assert result.metadata == {}


def test_null_provider_does_not_mutate_book() -> None:
    """Enrichment must leave the input Book unchanged."""
    book = _sample_book()
    original = (book.isbn, book.title, book.author, book.copies)
    NullBookEnrichmentProvider().enrich(book)
    assert (book.isbn, book.title, book.author, book.copies) == original


# --- Service delegation ------------------------------------------------------


def test_service_defaults_to_null_provider() -> None:
    """Service without an injected provider should use the null provider."""
    service = BookEnrichmentService()
    assert isinstance(service.provider, NullBookEnrichmentProvider)
    result = service.enrich(_sample_book())
    assert result.status is BookEnrichmentStatus.SKIPPED


def test_service_delegates_to_injected_provider() -> None:
    """Service should forward enrich() calls to the configured provider."""
    service = BookEnrichmentService(provider=_StubFoundProvider())
    book = _sample_book()
    result = service.enrich(book)

    assert result.status is BookEnrichmentStatus.FOUND
    assert result.title == "Resolved Title"
    assert result.author == "Resolved Author"
    assert result.metadata["publisher"] == "Stub Press"


def test_service_enrich_many_preserves_order() -> None:
    """enrich_many should return one result per book in input order."""
    books = [
        Book(isbn="9780064400558", title="A", author="B"),
        Book(isbn="9780060256654", title="C", author="D"),
    ]
    service = BookEnrichmentService(provider=_StubNotFoundProvider())
    results = service.enrich_many(books)

    assert [r.isbn for r in results] == [b.isbn for b in books]
    assert all(r.status is BookEnrichmentStatus.NOT_FOUND for r in results)


def test_service_enrich_many_empty() -> None:
    """Empty collections should yield an empty result list."""
    assert BookEnrichmentService().enrich_many([]) == []


# --- Future provider compatibility -------------------------------------------


def test_stub_provider_satisfies_protocol() -> None:
    """Structural stubs should be usable as BookEnrichmentProvider values."""
    provider: BookEnrichmentProvider = _StubFoundProvider()
    service = BookEnrichmentService(provider=provider)
    result = service.enrich(_sample_book())
    assert result.status is BookEnrichmentStatus.FOUND


@pytest.mark.parametrize(
    "status",
    [
        BookEnrichmentStatus.FOUND,
        BookEnrichmentStatus.NOT_FOUND,
        BookEnrichmentStatus.SKIPPED,
        BookEnrichmentStatus.AMBIGUOUS,
        BookEnrichmentStatus.ERROR,
    ],
)
def test_future_provider_can_return_any_status(
    status: BookEnrichmentStatus,
) -> None:
    """Providers may return any defined status without changing the service."""

    class _StatusProvider:
        def enrich(self, book: Book) -> BookEnrichmentResult:
            return BookEnrichmentResult(isbn=book.isbn, status=status)

    result = BookEnrichmentService(provider=_StatusProvider()).enrich(_sample_book())
    assert result.status is status


# --- In-memory enrichment cache ----------------------------------------------


class _CountingProvider:
    """Provider that records call count and returns a fixed status."""

    def __init__(
        self,
        status: BookEnrichmentStatus = BookEnrichmentStatus.FOUND,
        *,
        message: str = "counted",
    ) -> None:
        self.calls = 0
        self.status = status
        self.message = message
        self.books: list[Book] = []

    def enrich(self, book: Book) -> BookEnrichmentResult:
        self.calls += 1
        self.books.append(book)
        return BookEnrichmentResult(
            isbn=book.isbn,
            status=self.status,
            title=book.title,
            author=book.author,
            message=self.message,
        )


def test_repeated_identical_books_invoke_provider_once() -> None:
    """Same title/author should hit the provider only on the first enrich."""
    provider = _CountingProvider()
    service = BookEnrichmentService(provider=provider)
    book = _sample_book()

    first = service.enrich(book)
    second = service.enrich(book)

    assert provider.calls == 1
    assert first is second
    assert service.cache_hits == 1
    assert service.cache_misses == 1
    assert service.cache_size == 1


def test_different_books_bypass_the_cache() -> None:
    """Distinct title/author pairs each miss the cache."""
    provider = _CountingProvider()
    service = BookEnrichmentService(provider=provider)

    service.enrich(Book(isbn="1", title="Alpha", author="One"))
    service.enrich(Book(isbn="2", title="Beta", author="Two"))

    assert provider.calls == 2
    assert service.cache_hits == 0
    assert service.cache_misses == 2
    assert service.cache_size == 2


def test_normalization_shares_cache_across_equivalent_titles() -> None:
    """Punctuation/case variants of the same work share one cache entry."""
    provider = _CountingProvider()
    service = BookEnrichmentService(provider=provider)

    service.enrich(
        Book(isbn="1", title="Charlotte's Web", author="E. B. White")
    )
    service.enrich(
        Book(isbn="2", title="  CHARLOTTES WEB! ", author="e b white")
    )

    assert provider.calls == 1
    assert service.cache_hits == 1
    assert service.cache_misses == 1


def test_cache_ignores_isbn_differences() -> None:
    """ISBN is not part of the cache key (missing-ISBN rows still share)."""
    provider = _CountingProvider()
    service = BookEnrichmentService(provider=provider)

    service.enrich(
        Book(isbn="pending", title="Same Title", author="Same Author")
    )
    service.enrich(
        Book(isbn="9780064400558", title="Same Title", author="Same Author")
    )

    assert provider.calls == 1
    assert service.cache_hits == 1


def test_cache_hit_does_not_mutate_book() -> None:
    """Returning a cached result must leave the caller's Book untouched."""
    provider = _CountingProvider()
    service = BookEnrichmentService(provider=provider)
    book = _sample_book()
    original = book.to_dict()

    service.enrich(book)
    service.enrich(book)

    assert book.to_dict() == original
    assert provider.calls == 1


@pytest.mark.parametrize(
    "status",
    [
        BookEnrichmentStatus.FOUND,
        BookEnrichmentStatus.NOT_FOUND,
        BookEnrichmentStatus.AMBIGUOUS,
        BookEnrichmentStatus.ERROR,
        BookEnrichmentStatus.SKIPPED,
    ],
)
def test_all_result_statuses_are_cached(status: BookEnrichmentStatus) -> None:
    """FOUND / NOT_FOUND / AMBIGUOUS / ERROR / SKIPPED are all cached."""
    provider = _CountingProvider(status=status, message=status.value)
    service = BookEnrichmentService(provider=provider)
    book = _sample_book()

    first = service.enrich(book)
    second = service.enrich(book)

    assert first.status is status
    assert second.status is status
    assert provider.calls == 1
    assert service.cache_hits == 1
    assert service.cache_misses == 1


def test_enrich_many_uses_cache_across_duplicates() -> None:
    """Batch enrichment should reuse cache entries within the same run."""
    provider = _CountingProvider(status=BookEnrichmentStatus.NOT_FOUND)
    service = BookEnrichmentService(provider=provider)
    books = [
        Book(isbn="1", title="Dup", author="Author"),
        Book(isbn="2", title="Other", author="Author"),
        Book(isbn="3", title="Dup", author="Author"),
    ]

    results = service.enrich_many(books)

    assert provider.calls == 2
    assert service.cache_hits == 1
    assert service.cache_misses == 2
    assert results[0] is results[2]
    assert results[0].status is BookEnrichmentStatus.NOT_FOUND
