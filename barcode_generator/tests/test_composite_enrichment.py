"""Tests for CompositeBookEnrichmentProvider (stub providers; no network)."""

from __future__ import annotations

import logging

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
from classroom_library_label_maker.services.lookups.google_books import (
    GoogleBooksEnrichmentProvider,
)
from classroom_library_label_maker.services.protocols import BookEnrichmentProvider


def _book(
    *,
    title: str = "Charlotte's Web",
    author: str = "E. B. White",
) -> Book:
    return Book(isbn="MISSING", title=title, author=author, copies=1)


class _StubProvider:
    """Scripted enrichment provider for composite tests."""

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


def _result(
    status: BookEnrichmentStatus,
    *,
    isbn: str = "MISSING",
    message: str = "",
) -> BookEnrichmentResult:
    return BookEnrichmentResult(
        isbn=isbn,
        status=status,
        title=None,
        author=None,
        message=message or status.value,
        metadata={"provider": "stub"},
    )


def test_first_provider_found_returns_immediately() -> None:
    calls: list[str] = []
    composite = CompositeBookEnrichmentProvider(
        (
            _StubProvider(
                name="First",
                result=_result(BookEnrichmentStatus.FOUND, isbn="9780064400558"),
                calls=calls,
            ),
            _StubProvider(
                name="Second",
                result=_result(BookEnrichmentStatus.FOUND, isbn="9781111111111"),
                calls=calls,
            ),
        )
    )
    result = composite.enrich(_book())
    assert result.status is BookEnrichmentStatus.FOUND
    assert result.isbn == "9780064400558"
    assert calls == ["First"]


def test_first_provider_ambiguous_returns_immediately() -> None:
    calls: list[str] = []
    composite = CompositeBookEnrichmentProvider(
        (
            _StubProvider(
                name="First",
                result=_result(BookEnrichmentStatus.AMBIGUOUS, isbn="9780064400558"),
                calls=calls,
            ),
            _StubProvider(
                name="Second",
                result=_result(BookEnrichmentStatus.FOUND, isbn="9781111111111"),
                calls=calls,
            ),
        )
    )
    result = composite.enrich(_book())
    assert result.status is BookEnrichmentStatus.AMBIGUOUS
    assert calls == ["First"]


def test_not_found_then_second_found() -> None:
    calls: list[str] = []
    composite = CompositeBookEnrichmentProvider(
        (
            _StubProvider(
                name="First",
                result=_result(BookEnrichmentStatus.NOT_FOUND, message="miss"),
                calls=calls,
            ),
            _StubProvider(
                name="Second",
                result=_result(BookEnrichmentStatus.FOUND, isbn="9780374302030"),
                calls=calls,
            ),
        )
    )
    result = composite.enrich(_book())
    assert result.status is BookEnrichmentStatus.FOUND
    assert result.isbn == "9780374302030"
    assert calls == ["First", "Second"]


def test_error_then_second_found() -> None:
    calls: list[str] = []
    composite = CompositeBookEnrichmentProvider(
        (
            _StubProvider(
                name="First",
                result=_result(BookEnrichmentStatus.ERROR, message="timeout"),
                calls=calls,
            ),
            _StubProvider(
                name="Second",
                result=_result(BookEnrichmentStatus.FOUND, isbn="9780374302030"),
                calls=calls,
            ),
        )
    )
    result = composite.enrich(_book())
    assert result.status is BookEnrichmentStatus.FOUND
    assert result.isbn == "9780374302030"
    assert calls == ["First", "Second"]


def test_all_providers_not_found() -> None:
    composite = CompositeBookEnrichmentProvider(
        (
            _StubProvider(
                name="First",
                result=_result(BookEnrichmentStatus.NOT_FOUND, message="a"),
            ),
            _StubProvider(
                name="Second",
                result=_result(BookEnrichmentStatus.NOT_FOUND, message="b"),
            ),
        )
    )
    result = composite.enrich(_book())
    assert result.status is BookEnrichmentStatus.NOT_FOUND
    assert result.metadata["provider"] == "composite"


def test_all_errors_become_not_found() -> None:
    composite = CompositeBookEnrichmentProvider(
        (
            _StubProvider(
                name="First",
                result=_result(BookEnrichmentStatus.ERROR, message="boom"),
            ),
            _StubProvider(
                name="Second",
                result=_result(BookEnrichmentStatus.ERROR, message="boom2"),
            ),
        )
    )
    result = composite.enrich(_book())
    assert result.status is BookEnrichmentStatus.NOT_FOUND
    assert result.message == "boom2"


def test_provider_ordering_respected() -> None:
    calls: list[str] = []
    composite = CompositeBookEnrichmentProvider(
        (
            _StubProvider(
                name="Alpha",
                result=_result(BookEnrichmentStatus.NOT_FOUND),
                calls=calls,
            ),
            _StubProvider(
                name="Beta",
                result=_result(BookEnrichmentStatus.NOT_FOUND),
                calls=calls,
            ),
            _StubProvider(
                name="Gamma",
                result=_result(BookEnrichmentStatus.FOUND, isbn="9780000000001"),
                calls=calls,
            ),
        )
    )
    result = composite.enrich(_book())
    assert result.status is BookEnrichmentStatus.FOUND
    assert calls == ["Alpha", "Beta", "Gamma"]
    assert [p.provider_name for p in composite.providers] == [
        "Alpha",
        "Beta",
        "Gamma",
    ]


def test_empty_providers_rejected() -> None:
    with pytest.raises(ValueError, match="at least one provider"):
        CompositeBookEnrichmentProvider(())


def test_composite_is_protocol_compatible() -> None:
    provider: BookEnrichmentProvider = CompositeBookEnrichmentProvider(
        (
            _StubProvider(
                name="Only",
                result=_result(BookEnrichmentStatus.FOUND, isbn="9780064400558"),
            ),
        )
    )
    result = provider.enrich(_book())
    assert result.status is BookEnrichmentStatus.FOUND


def test_service_cache_still_applies_to_composite() -> None:
    calls: list[str] = []
    composite = CompositeBookEnrichmentProvider(
        (
            _StubProvider(
                name="Only",
                result=_result(BookEnrichmentStatus.FOUND, isbn="9780064400558"),
                calls=calls,
            ),
        )
    )
    service = BookEnrichmentService(provider=composite)
    book = _book()
    assert service.enrich(book).status is BookEnrichmentStatus.FOUND
    assert service.enrich(book).status is BookEnrichmentStatus.FOUND
    assert calls == ["Only"]
    assert service.cache_hits == 1
    assert service.cache_misses == 1


def test_create_default_uses_composite_with_google_books() -> None:
    service = create_default_enrichment_service(api_key="test-key")
    provider = service.provider
    assert isinstance(provider, CompositeBookEnrichmentProvider)
    assert len(provider.providers) == 1
    inner = provider.providers[0]
    assert isinstance(inner, GoogleBooksEnrichmentProvider)
    assert inner.uses_authentication is True


def test_debug_diagnostics_show_continuation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    composite = CompositeBookEnrichmentProvider(
        (
            _StubProvider(
                name="Google Books",
                result=_result(BookEnrichmentStatus.NOT_FOUND),
            ),
            _StubProvider(
                name="Open Library",
                result=_result(BookEnrichmentStatus.FOUND, isbn="9780374302030"),
            ),
        )
    )
    with caplog.at_level(
        logging.DEBUG,
        logger="classroom_library_label_maker.composite_enrichment",
    ):
        result = composite.enrich(_book())

    assert result.status is BookEnrichmentStatus.FOUND
    joined = "\n".join(record.getMessage() for record in caplog.records)
    assert "Google Books" in joined
    assert "not_found" in joined
    assert "Continuing..." in joined
    assert "Open Library" in joined
    assert "Returning." in joined
    assert "key=" not in joined.lower()
