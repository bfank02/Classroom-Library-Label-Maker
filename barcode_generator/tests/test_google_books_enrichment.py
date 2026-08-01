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
    RATE_LIMIT_USER_MESSAGE,
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
    """Title + inauthor:surname hit with strong scores should return FOUND."""
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
    assert "inauthor:White" in _query_from_url(fetcher.urls[0])
    assert "Charlotte" in _query_from_url(fetcher.urls[0])


def test_title_only_match_after_empty_combined_query() -> None:
    """Fall through to free-text / title-only when surname query is empty."""
    fetcher = _ScriptedFetcher(
        [
            _payload(),  # title inauthor:surname empty
            _payload(),  # title + author empty
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
    assert len(fetcher.urls) == 3
    assert _query_from_url(fetcher.urls[2]) == "Charlotte's Web"


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
    assert queries[0] == "Charlotte's Web inauthor:White"
    assert queries[1] == "Charlotte's Web E. B. White"
    assert queries[2] == "Charlotte's Web"


def test_build_queries_prefers_surname_inauthor() -> None:
    from classroom_library_label_maker.services.lookups.google_books import (
        _author_surname,
        _build_queries,
    )

    assert _author_surname("E. B. White") == "White"
    assert _author_surname("White, E. B.") == "White"
    assert _author_surname("Dr. Seuss") == "Seuss"
    queries = _build_queries("Charlotte's Web", "E. B. White")
    assert queries[0] == "Charlotte's Web inauthor:White"
    assert "Charlotte's Web E. B. White" in queries
    assert "Charlotte's Web" in queries


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


def test_free_text_query_used_second() -> None:
    """Free-text title+author runs after surname query misses."""
    fetcher = _ScriptedFetcher(
        [
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
    assert len(fetcher.urls) == 2
    assert _query_from_url(fetcher.urls[1]) == "Charlotte's Web E. B. White"


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
    assert all("Title" in q for q in queries)
    assert not any(q.strip().startswith("inauthor:") for q in queries)
    assert not any(q == 'inauthor:"Author"' for q in queries)


def test_live_fetch_retries_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP 429 should back off and retry before failing."""
    from classroom_library_label_maker.services.lookups import google_books as gb

    calls = {"n": 0}
    sleeps: list[float] = []

    def fake_fetch(url: str, *, timeout_seconds: float) -> dict[str, object]:
        calls["n"] += 1
        if calls["n"] < 3:
            raise GoogleBooksTransportError(
                RATE_LIMIT_USER_MESSAGE,
                kind="rate_limit",
            )
        return _payload(
            _volume(
                volume_id="v",
                title="Charlotte's Web",
                authors=["E. B. White"],
                isbn13="9780064400558",
            )
        )

    monkeypatch.setattr(gb, "_default_fetch_json", fake_fetch)
    provider = GoogleBooksEnrichmentProvider(
        min_request_interval_seconds=0,
        max_retries_on_429=4,
        rate_limit_backoff_seconds=0.5,
        rate_limit_max_backoff_seconds=8.0,
        sleep=sleeps.append,
    )
    result = provider.enrich(_book())
    assert result.status is BookEnrichmentStatus.FOUND
    assert calls["n"] == 3
    assert sleeps == [0.5, 1.0]


def test_live_fetch_429_backoff_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    """429 backoff should not grow past ``rate_limit_max_backoff_seconds``."""
    from classroom_library_label_maker.services.lookups import google_books as gb

    calls = {"n": 0}
    sleeps: list[float] = []

    def fake_fetch(url: str, *, timeout_seconds: float) -> dict[str, object]:
        calls["n"] += 1
        if calls["n"] < 5:
            raise GoogleBooksTransportError(
                RATE_LIMIT_USER_MESSAGE,
                kind="rate_limit",
            )
        return _payload(
            _volume(
                volume_id="v",
                title="Charlotte's Web",
                authors=["E. B. White"],
                isbn13="9780064400558",
            )
        )

    monkeypatch.setattr(gb, "_default_fetch_json", fake_fetch)
    provider = GoogleBooksEnrichmentProvider(
        min_request_interval_seconds=0,
        max_retries_on_429=4,
        rate_limit_backoff_seconds=2.0,
        rate_limit_max_backoff_seconds=3.0,
        sleep=sleeps.append,
    )
    result = provider.enrich(_book())
    assert result.status is BookEnrichmentStatus.FOUND
    assert sleeps == [2.0, 3.0, 3.0, 3.0]


def test_exhausted_429_uses_friendly_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from classroom_library_label_maker.services.lookups import google_books as gb

    def always_429(url: str, *, timeout_seconds: float) -> dict[str, object]:
        raise GoogleBooksTransportError(
            RATE_LIMIT_USER_MESSAGE,
            kind="rate_limit",
        )

    monkeypatch.setattr(gb, "_default_fetch_json", always_429)
    provider = GoogleBooksEnrichmentProvider(
        min_request_interval_seconds=0,
        max_retries_on_429=1,
        rate_limit_backoff_seconds=0.1,
        rate_limit_max_backoff_seconds=0.1,
        rate_limit_circuit_breaker_threshold=99,
        sleep=lambda _s: None,
    )
    result = provider.enrich(_book())
    assert result.status is BookEnrichmentStatus.ERROR
    assert result.metadata["error_kind"] == "rate_limit"
    assert "rate limit" in result.message.lower()
    assert "429" not in result.message


def test_rate_limit_circuit_skips_further_lookups(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from classroom_library_label_maker.services.lookups import google_books as gb
    from classroom_library_label_maker.services.lookups.google_books import (
        RATE_LIMIT_STOPPED_MESSAGE,
    )

    calls = {"n": 0}

    def always_429(url: str, *, timeout_seconds: float) -> dict[str, object]:
        calls["n"] += 1
        raise GoogleBooksTransportError(
            RATE_LIMIT_USER_MESSAGE,
            kind="rate_limit",
        )

    monkeypatch.setattr(gb, "_default_fetch_json", always_429)
    provider = GoogleBooksEnrichmentProvider(
        min_request_interval_seconds=0,
        max_retries_on_429=0,
        rate_limit_backoff_seconds=0.1,
        rate_limit_max_backoff_seconds=0.1,
        rate_limit_circuit_breaker_threshold=2,
        sleep=lambda _s: None,
    )
    first = provider.enrich(_book(title="One"))
    second = provider.enrich(_book(title="Two"))
    third = provider.enrich(_book(title="Three"))
    assert first.status is BookEnrichmentStatus.ERROR
    assert second.status is BookEnrichmentStatus.ERROR
    assert third.status is BookEnrichmentStatus.ERROR
    assert second.message == RATE_LIMIT_STOPPED_MESSAGE
    assert third.message == RATE_LIMIT_STOPPED_MESSAGE
    assert third.metadata.get("circuit_open") is True
    # No successful responses yet → circuit opens after the first book fails.
    assert calls["n"] == 1


def test_live_fetch_paces_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    from classroom_library_label_maker.services.lookups import google_books as gb

    sleeps: list[float] = []
    clock = {"t": 1000.0}

    def fake_monotonic() -> float:
        return clock["t"]

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock["t"] += seconds

    def fake_fetch(url: str, *, timeout_seconds: float) -> dict[str, object]:
        clock["t"] += 0.01  # tiny elapsed work between requests
        return _payload()

    monkeypatch.setattr(gb.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gb, "_default_fetch_json", fake_fetch)
    provider = GoogleBooksEnrichmentProvider(
        min_request_interval_seconds=0.75,
        sleep=fake_sleep,
    )
    result = provider.enrich(_book())
    assert result.status is BookEnrichmentStatus.NOT_FOUND
    assert len(sleeps) >= 2
    assert all(pause == pytest.approx(0.74, abs=0.02) for pause in sleeps)


def test_injected_fetch_json_skips_rate_limiting() -> None:
    sleeps: list[float] = []
    fetcher = _ScriptedFetcher([_payload(), _payload(), _payload()])
    provider = GoogleBooksEnrichmentProvider(
        fetch_json=fetcher,
        min_request_interval_seconds=0.75,
        sleep=sleeps.append,
    )
    provider.enrich(_book())
    assert sleeps == []


def test_authenticated_requests_append_key_parameter() -> None:
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
    provider = GoogleBooksEnrichmentProvider(
        api_key="secret-test-key",
        fetch_json=fetcher,
    )
    result = provider.enrich(_book())
    assert result.status is BookEnrichmentStatus.FOUND
    assert fetcher.urls
    params = parse_qs(urlparse(fetcher.urls[0]).query)
    assert params.get("key") == ["secret-test-key"]


def test_anonymous_requests_omit_key_parameter() -> None:
    fetcher = _ScriptedFetcher([_payload()])
    provider = GoogleBooksEnrichmentProvider(fetch_json=fetcher)
    provider.enrich(_book())
    params = parse_qs(urlparse(fetcher.urls[0]).query)
    assert "key" not in params


def test_authenticated_default_pacing_is_faster_than_anonymous() -> None:
    from classroom_library_label_maker.services.lookups.google_books import (
        DEFAULT_ANONYMOUS_MIN_REQUEST_INTERVAL_SECONDS,
        DEFAULT_AUTHENTICATED_MIN_REQUEST_INTERVAL_SECONDS,
    )

    authenticated = GoogleBooksEnrichmentProvider(api_key="k")
    anonymous = GoogleBooksEnrichmentProvider()
    assert (
        authenticated.min_request_interval_seconds
        == DEFAULT_AUTHENTICATED_MIN_REQUEST_INTERVAL_SECONDS
    )
    assert (
        anonymous.min_request_interval_seconds
        == DEFAULT_ANONYMOUS_MIN_REQUEST_INTERVAL_SECONDS
    )
    assert (
        authenticated.min_request_interval_seconds
        < anonymous.min_request_interval_seconds
    )


def test_adaptive_slowdown_still_functions_when_authenticated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from classroom_library_label_maker.services.lookups import google_books as gb

    calls = {"n": 0}
    sleeps: list[float] = []

    def fake_fetch(url: str, *, timeout_seconds: float) -> dict[str, object]:
        calls["n"] += 1
        if calls["n"] == 1:
            raise GoogleBooksTransportError(
                RATE_LIMIT_USER_MESSAGE,
                kind="rate_limit",
            )
        return _payload(
            _volume(
                volume_id="v",
                title="Charlotte's Web",
                authors=["E. B. White"],
                isbn13="9780064400558",
            )
        )

    monkeypatch.setattr(gb, "_default_fetch_json", fake_fetch)
    provider = GoogleBooksEnrichmentProvider(
        api_key="k",
        min_request_interval_seconds=0.4,
        max_retries_on_429=2,
        rate_limit_backoff_seconds=0.1,
        rate_limit_max_backoff_seconds=0.1,
        adaptive_max_interval_seconds=2.0,
        sleep=sleeps.append,
    )
    before = provider.min_request_interval_seconds
    result = provider.enrich(_book())
    assert result.status is BookEnrichmentStatus.FOUND
    assert provider.min_request_interval_seconds > before
    assert provider.rate_limit_response_count >= 1


def test_auth_failure_falls_back_to_anonymous() -> None:
    secret = "reject-me-key"
    responses: list[dict[str, Any] | BaseException] = [
        GoogleBooksTransportError("rejected", kind="auth"),
        _payload(
            _volume(
                volume_id="v",
                title="Charlotte's Web",
                authors=["E. B. White"],
                isbn13="9780064400558",
            )
        ),
    ]
    fetcher = _ScriptedFetcher(responses)
    provider = GoogleBooksEnrichmentProvider(api_key=secret, fetch_json=fetcher)
    result = provider.enrich(_book())
    assert result.status is BookEnrichmentStatus.FOUND
    assert provider.uses_authentication is False
    assert len(fetcher.urls) == 2
    first = parse_qs(urlparse(fetcher.urls[0]).query)
    second = parse_qs(urlparse(fetcher.urls[1]).query)
    assert first.get("key") == [secret]
    assert "key" not in second


def test_auth_failure_does_not_retry_invalid_key_repeatedly() -> None:
    secret = "bad-key"
    fetcher = _ScriptedFetcher(
        [
            GoogleBooksTransportError("rejected", kind="auth"),
            GoogleBooksTransportError("rejected", kind="auth"),
        ]
    )
    provider = GoogleBooksEnrichmentProvider(api_key=secret, fetch_json=fetcher)
    result = provider.enrich(_book())
    assert result.status is BookEnrichmentStatus.ERROR
    assert result.metadata["error_kind"] == "auth"
    # One authenticated attempt + one anonymous fallback attempt only.
    assert len(fetcher.urls) == 2
    assert parse_qs(urlparse(fetcher.urls[0]).query).get("key") == [secret]
    assert "key" not in parse_qs(urlparse(fetcher.urls[1]).query)


def test_api_key_never_appears_in_provider_log_records(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "super-secret-api-key-xyz"
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
    provider = GoogleBooksEnrichmentProvider(api_key=secret, fetch_json=fetcher)
    with caplog.at_level("DEBUG"):
        provider.enrich(_book())
    joined = "\n".join(record.getMessage() for record in caplog.records)
    assert secret not in joined
    assert "Google Books requests: Authenticated" in joined
