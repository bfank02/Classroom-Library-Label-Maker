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
