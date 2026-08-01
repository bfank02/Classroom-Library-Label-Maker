"""Google Books catalog enrichment provider.

Implements
:class:`~classroom_library_label_maker.services.protocols.BookEnrichmentProvider`
using the public Google Books Volumes API. HTTP and Google response shapes stay
inside this module - callers only see :class:`BookEnrichmentResult`.

Used by
:func:`~classroom_library_label_maker.services.book_enrichment_service.create_default_enrichment_service`
when missing-ISBN lookup is enabled. Inject explicitly in tests::

    BookEnrichmentService(provider=GoogleBooksEnrichmentProvider())
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
import json
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.metadata import APP_NAME, APP_VERSION
from classroom_library_label_maker.models import (
    Book,
    BookEnrichmentResult,
    BookEnrichmentStatus,
    ReviewCandidate,
)
from classroom_library_label_maker.services.enrichment_normalize import (
    normalize_catalog_text,
)

_logger = get_logger("google_books")

GOOGLE_BOOKS_VOLUMES_URL = "https://www.googleapis.com/books/v1/volumes"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_RESULTS = 10
# Anonymous pacing stays under the common ~100 queries/minute quota. Each
# missing ISBN can issue up to three searches, so pace conservatively.
DEFAULT_ANONYMOUS_MIN_REQUEST_INTERVAL_SECONDS = 1.25
# Authenticated keys still have per-user quotas; pace faster but not unbounded.
DEFAULT_AUTHENTICATED_MIN_REQUEST_INTERVAL_SECONDS = 0.40
# Backward-compatible alias (anonymous default).
DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = DEFAULT_ANONYMOUS_MIN_REQUEST_INTERVAL_SECONDS
DEFAULT_MAX_RETRIES_ON_429 = 6
DEFAULT_429_INITIAL_BACKOFF_SECONDS = 5.0
DEFAULT_429_MAX_BACKOFF_SECONDS = 65.0
DEFAULT_429_CIRCUIT_BREAKER_THRESHOLD = 3
DEFAULT_ADAPTIVE_MAX_INTERVAL_SECONDS = 3.0
RATE_LIMIT_USER_MESSAGE = (
    "Google Books rate limit reached. Try again in a few minutes, "
    "or set GOOGLE_BOOKS_API_KEY for higher quota."
)
RATE_LIMIT_STOPPED_MESSAGE = (
    "ISBN lookup stopped: Google Books rate limit. "
    "Try again later or set GOOGLE_BOOKS_API_KEY."
)
AUTH_FAILURE_USER_MESSAGE = (
    "Google Books API key was rejected. Continuing without authentication."
)

# Match selection thresholds (combined confidence score in [0, 1]).
_FOUND_THRESHOLD = 0.85
_CONSIDER_THRESHOLD = 0.72
_AMBIGUOUS_MARGIN = 0.06
_EDITION_TITLE_THRESHOLD = 0.92
_EDITION_AUTHOR_THRESHOLD = 0.80

_WHITESPACE_RE = re.compile(r"\s+")

JsonFetcher = Callable[[str], Mapping[str, Any]]
"""Callable that GETs a URL and returns parsed JSON (no HTTP types leaked)."""


class GoogleBooksTransportError(Exception):
    """Internal transport / parse failure; never raised out of ``enrich``."""

    def __init__(
        self,
        message: str,
        *,
        kind: str = "error",
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.retry_after_seconds = retry_after_seconds


def _retry_after_seconds(exc: HTTPError) -> float | None:
    """Parse a numeric ``Retry-After`` header when present."""
    try:
        raw = exc.headers.get("Retry-After") if exc.headers is not None else None
    except Exception:
        return None
    if raw is None:
        return None
    try:
        value = float(str(raw).strip())
    except ValueError:
        return None
    if value < 0:
        return None
    return value


@dataclass(frozen=True, slots=True)
class _VolumeCandidate:
    """Internal catalog candidate mapped from a Google Books volume."""

    title: str
    authors: tuple[str, ...]
    isbn13: str | None
    isbn10: str | None
    volume_id: str
    publisher: str | None
    published_date: str | None
    raw_title: str


@dataclass(frozen=True, slots=True)
class _ScoredCandidate:
    """Candidate plus confidence against the query book."""

    candidate: _VolumeCandidate
    title_score: float
    author_score: float
    confidence: float


# Re-export for callers that historically imported from this module.
__all__ = [
    "AUTH_FAILURE_USER_MESSAGE",
    "DEFAULT_429_CIRCUIT_BREAKER_THRESHOLD",
    "DEFAULT_429_INITIAL_BACKOFF_SECONDS",
    "DEFAULT_429_MAX_BACKOFF_SECONDS",
    "DEFAULT_ADAPTIVE_MAX_INTERVAL_SECONDS",
    "DEFAULT_ANONYMOUS_MIN_REQUEST_INTERVAL_SECONDS",
    "DEFAULT_AUTHENTICATED_MIN_REQUEST_INTERVAL_SECONDS",
    "DEFAULT_MAX_RESULTS",
    "DEFAULT_MAX_RETRIES_ON_429",
    "DEFAULT_MIN_REQUEST_INTERVAL_SECONDS",
    "DEFAULT_TIMEOUT_SECONDS",
    "GOOGLE_BOOKS_VOLUMES_URL",
    "RATE_LIMIT_STOPPED_MESSAGE",
    "RATE_LIMIT_USER_MESSAGE",
    "GoogleBooksEnrichmentProvider",
    "GoogleBooksTransportError",
    "JsonFetcher",
    "author_similarity",
    "combined_confidence",
    "normalize_catalog_text",
    "title_similarity",
]


def _similarity(left: str, right: str) -> float:
    """Return a [0, 1] similarity ratio for two already-normalized strings."""
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    ratio = SequenceMatcher(None, left, right).ratio()
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if left_tokens and right_tokens:
        jaccard = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
        ratio = max(ratio, jaccard)
    if left in right or right in left:
        ratio = max(ratio, 0.9)
    return ratio


def title_similarity(query_title: str, candidate_title: str) -> float:
    """Score title similarity after normalization."""
    return _similarity(
        normalize_catalog_text(query_title),
        normalize_catalog_text(candidate_title),
    )


def author_similarity(query_author: str, candidate_authors: Sequence[str]) -> float:
    """Score author similarity against one or more candidate author names."""
    query = normalize_catalog_text(query_author)
    if not query:
        return 0.0
    best = 0.0
    for author in candidate_authors:
        best = max(best, _similarity(query, normalize_catalog_text(author)))
    return best


def combined_confidence(title_score: float, author_score: float) -> float:
    """Weight title more heavily than author for overall confidence."""
    return (0.65 * title_score) + (0.35 * author_score)


def _default_fetch_json(url: str, *, timeout_seconds: float) -> Mapping[str, Any]:
    """GET ``url`` with urllib and return parsed JSON.

    Raises:
        GoogleBooksTransportError: On timeout, HTTP failure, or bad JSON.
    """
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": f"{APP_NAME}/{APP_VERSION}",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read()
    except TimeoutError as exc:
        raise GoogleBooksTransportError(
            "Google Books request timed out",
            kind="timeout",
        ) from exc
    except HTTPError as exc:
        if exc.code == 429:
            raise GoogleBooksTransportError(
                RATE_LIMIT_USER_MESSAGE,
                kind="rate_limit",
                retry_after_seconds=_retry_after_seconds(exc),
            ) from exc
        if exc.code in {401, 403}:
            raise GoogleBooksTransportError(
                AUTH_FAILURE_USER_MESSAGE,
                kind="auth",
            ) from exc
        raise GoogleBooksTransportError(
            f"Google Books HTTP error: {exc.code}",
            kind="http",
        ) from exc
    except URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
            raise GoogleBooksTransportError(
                "Google Books request timed out",
                kind="timeout",
            ) from exc
        raise GoogleBooksTransportError(
            f"Google Books network error: {reason}",
            kind="network",
        ) from exc
    except OSError as exc:
        raise GoogleBooksTransportError(
            f"Google Books network error: {exc}",
            kind="network",
        ) from exc

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GoogleBooksTransportError(
            "Google Books response was not valid JSON",
            kind="malformed",
        ) from exc

    if not isinstance(payload, dict):
        raise GoogleBooksTransportError(
            "Google Books response JSON must be an object",
            kind="malformed",
        )
    return payload


def _build_queries(title: str, author: str) -> tuple[str, ...]:
    """Return ordered Google Books ``q`` values (no author-only search)."""
    title = title.strip()
    author = author.strip()
    queries: list[str] = []
    if title and author:
        queries.append(f'intitle:"{title}" inauthor:"{author}"')
    if title:
        queries.append(f'intitle:"{title}"')
    if title and author:
        queries.append(f"{title} {author}")
    return tuple(queries)


def _extract_isbns(
    identifiers: Sequence[Mapping[str, Any]] | None,
) -> tuple[str | None, str | None]:
    """Return ``(isbn13, isbn10)`` from Google ``industryIdentifiers``."""
    isbn13: str | None = None
    isbn10: str | None = None
    if not identifiers:
        return None, None
    for item in identifiers:
        if not isinstance(item, Mapping):
            continue
        id_type = str(item.get("type", "")).upper()
        raw_id = str(item.get("identifier", "")).strip()
        value = raw_id.replace("-", "").replace(" ", "")
        if not value:
            continue
        if id_type == "ISBN_13" and len(value) == 13 and value.isdigit():
            isbn13 = value
        elif id_type == "ISBN_10" and len(value) == 10:
            isbn10 = value
    return isbn13, isbn10


def _parse_volume(item: Mapping[str, Any]) -> _VolumeCandidate | None:
    """Map one Google Books volume item to an internal candidate."""
    if not isinstance(item, Mapping):
        return None
    volume_info = item.get("volumeInfo")
    if not isinstance(volume_info, Mapping):
        return None
    raw_title = str(volume_info.get("title") or "").strip()
    if not raw_title:
        return None
    authors_raw = volume_info.get("authors") or []
    authors: list[str] = []
    if isinstance(authors_raw, Sequence) and not isinstance(authors_raw, (str, bytes)):
        for author in authors_raw:
            text = str(author).strip()
            if text:
                authors.append(text)
    isbn13, isbn10 = _extract_isbns(volume_info.get("industryIdentifiers"))
    volume_id = str(item.get("id") or "").strip()
    publisher = volume_info.get("publisher")
    published_date = volume_info.get("publishedDate")
    return _VolumeCandidate(
        title=_WHITESPACE_RE.sub(" ", raw_title).strip(),
        authors=tuple(authors),
        isbn13=isbn13,
        isbn10=isbn10,
        volume_id=volume_id,
        publisher=str(publisher).strip() if publisher else None,
        published_date=str(published_date).strip() if published_date else None,
        raw_title=raw_title,
    )


def _parse_volumes(payload: Mapping[str, Any]) -> list[_VolumeCandidate]:
    """Extract candidates from a volumes.list JSON payload."""
    items = payload.get("items")
    if items is None:
        return []
    if not isinstance(items, list):
        raise GoogleBooksTransportError(
            "Google Books response 'items' must be a list",
            kind="malformed",
        )
    candidates: list[_VolumeCandidate] = []
    for item in items:
        if isinstance(item, Mapping):
            parsed = _parse_volume(item)
            if parsed is not None:
                candidates.append(parsed)
    return candidates


def _score_candidate(book: Book, candidate: _VolumeCandidate) -> _ScoredCandidate:
    """Score one candidate against the inventory book."""
    title_score = title_similarity(book.title, candidate.title)
    author_score = author_similarity(book.author, candidate.authors)
    return _ScoredCandidate(
        candidate=candidate,
        title_score=title_score,
        author_score=author_score,
        confidence=combined_confidence(title_score, author_score),
    )


def _same_work(left: _ScoredCandidate, right: _ScoredCandidate) -> bool:
    """True when two candidates look like editions of the same work."""
    title_ok = (
        title_similarity(left.candidate.title, right.candidate.title)
        >= _EDITION_TITLE_THRESHOLD
    )
    if not title_ok:
        return False
    left_authors = ", ".join(left.candidate.authors)
    right_authors = ", ".join(right.candidate.authors)
    if not left_authors and not right_authors:
        return True
    return author_similarity(left_authors, right.candidate.authors) >= (
        _EDITION_AUTHOR_THRESHOLD
    )


def _prefer_edition(scored: Sequence[_ScoredCandidate]) -> _ScoredCandidate:
    """Prefer ISBN-13, then ISBN-10, then highest confidence."""

    def sort_key(item: _ScoredCandidate) -> tuple[int, int, float]:
        has13 = 1 if item.candidate.isbn13 else 0
        has10 = 1 if item.candidate.isbn10 else 0
        return (has13, has10, item.confidence)

    return max(scored, key=sort_key)


def _select_match(
    scored: Sequence[_ScoredCandidate],
) -> tuple[
    BookEnrichmentStatus,
    _ScoredCandidate | None,
    str,
    tuple[_ScoredCandidate, ...],
]:
    """Choose FOUND / AMBIGUOUS / NOT_FOUND from scored candidates.

    Returns ``(status, primary_match, message, ambiguous_peers)``. Peers are
    ordered by descending confidence and are non-empty only for ``AMBIGUOUS``.
    """
    viable = sorted(
        (item for item in scored if item.confidence >= _CONSIDER_THRESHOLD),
        key=lambda item: item.confidence,
        reverse=True,
    )
    if not viable:
        return (
            BookEnrichmentStatus.NOT_FOUND,
            None,
            "No sufficiently close matches",
            (),
        )

    best = viable[0]
    peers = [
        item
        for item in viable
        if best.confidence - item.confidence <= _AMBIGUOUS_MARGIN
    ]

    if len(peers) > 1:
        if all(_same_work(best, peer) for peer in peers[1:]):
            chosen = _prefer_edition(peers)
            if chosen.confidence >= _FOUND_THRESHOLD:
                return (
                    BookEnrichmentStatus.FOUND,
                    chosen,
                    "Matched among multiple editions",
                    (),
                )
        ordered_peers = tuple(
            sorted(peers, key=lambda item: item.confidence, reverse=True)
        )
        if best.confidence >= _FOUND_THRESHOLD:
            return (
                BookEnrichmentStatus.AMBIGUOUS,
                best,
                "Multiple distinct close matches",
                ordered_peers,
            )
        return (
            BookEnrichmentStatus.AMBIGUOUS,
            best,
            "Multiple weak close matches",
            ordered_peers,
        )

    if best.confidence >= _FOUND_THRESHOLD:
        return BookEnrichmentStatus.FOUND, best, "Confident single match", ()

    return (
        BookEnrichmentStatus.NOT_FOUND,
        None,
        "Best match below confidence threshold",
        (),
    )


def _format_authors(authors: Sequence[str]) -> str | None:
    if not authors:
        return None
    return ", ".join(authors)


def _to_review_candidate(scored: _ScoredCandidate) -> ReviewCandidate:
    """Map an internal scored volume to a public review candidate."""
    candidate = scored.candidate
    return ReviewCandidate(
        isbn13=candidate.isbn13,
        isbn10=candidate.isbn10,
        title=candidate.title,
        author=_format_authors(candidate.authors) or "",
        publisher=candidate.publisher,
        published_date=candidate.published_date,
        confidence_score=round(scored.confidence, 4),
    )


def _result_from_candidate(
    book: Book,
    status: BookEnrichmentStatus,
    scored: _ScoredCandidate | None,
    *,
    message: str,
    query: str | None = None,
    ambiguous_peers: Sequence[_ScoredCandidate] = (),
) -> BookEnrichmentResult:
    """Build a :class:`BookEnrichmentResult` without mutating ``book``."""
    review_candidates: tuple[ReviewCandidate, ...] = ()
    if status is BookEnrichmentStatus.AMBIGUOUS and ambiguous_peers:
        review_candidates = tuple(
            _to_review_candidate(peer) for peer in ambiguous_peers
        )

    if scored is None:
        return BookEnrichmentResult(
            isbn=book.isbn,
            status=status,
            title=None,
            author=None,
            message=message,
            metadata={
                "provider": "google_books",
                "query": query,
            },
            candidates=review_candidates,
        )

    candidate = scored.candidate
    resolved_isbn = candidate.isbn13 or candidate.isbn10 or book.isbn
    normalized_title = normalize_catalog_text(candidate.title)
    return BookEnrichmentResult(
        isbn=resolved_isbn,
        status=status,
        title=candidate.title,
        author=_format_authors(candidate.authors),
        message=message,
        metadata={
            "provider": "google_books",
            "isbn13": candidate.isbn13,
            "isbn10": candidate.isbn10,
            "authors": list(candidate.authors),
            "normalized_title": normalized_title,
            "normalized_author": normalize_catalog_text(
                _format_authors(candidate.authors) or ""
            ),
            "google_volume_id": candidate.volume_id or None,
            "publisher": candidate.publisher,
            "published_date": candidate.published_date,
            "confidence": round(scored.confidence, 4),
            "title_score": round(scored.title_score, 4),
            "author_score": round(scored.author_score, 4),
            "query": query,
            "source_isbn": book.isbn,
        },
        candidates=review_candidates,
    )


class GoogleBooksEnrichmentProvider:
    """Enrich books via Google Books title/author search.

    Search order (sequential requests; stops early on FOUND or AMBIGUOUS):

    1. ``intitle:"<title>" inauthor:"<author>"``
    2. ``intitle:"<title>"``
    3. ``<title> <author>``

    Never performs author-only searches. Transport failures become
    :attr:`BookEnrichmentStatus.ERROR` results - exceptions are not leaked.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_results: int = DEFAULT_MAX_RESULTS,
        api_key: str | None = None,
        fetch_json: JsonFetcher | None = None,
        min_request_interval_seconds: float | None = None,
        max_retries_on_429: int = DEFAULT_MAX_RETRIES_ON_429,
        rate_limit_backoff_seconds: float = DEFAULT_429_INITIAL_BACKOFF_SECONDS,
        rate_limit_max_backoff_seconds: float = DEFAULT_429_MAX_BACKOFF_SECONDS,
        rate_limit_circuit_breaker_threshold: int = (
            DEFAULT_429_CIRCUIT_BREAKER_THRESHOLD
        ),
        adaptive_max_interval_seconds: float | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        """Initialize the provider.

        Args:
            timeout_seconds: Per-request timeout.
            max_results: Google Books ``maxResults`` (1-40).
            api_key: Optional API key (caller-injected; origin unknown here).
            fetch_json: Injectable JSON GET for tests (receives full URL).
                When set, throttling / 429 retries are skipped (tests own timing).
            min_request_interval_seconds: Minimum delay between live HTTP calls
                (``0`` disables pacing). When omitted, uses authenticated or
                anonymous defaults based on whether ``api_key`` is set.
            max_retries_on_429: Extra attempts after HTTP 429 before failing.
            rate_limit_backoff_seconds: Initial sleep after a 429 (doubles each
                retry, capped by ``rate_limit_max_backoff_seconds``).
            rate_limit_max_backoff_seconds: Upper bound for 429 backoff sleeps.
            rate_limit_circuit_breaker_threshold: After this many consecutive
                book-level rate-limit failures, skip further live lookups.
            adaptive_max_interval_seconds: Cap when pacing slows after 429s.
                Defaults to at least the chosen base interval.
            sleep: Injectable sleeper for tests (defaults to :func:`time.sleep`).
        """
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not 1 <= max_results <= 40:
            raise ValueError("max_results must be between 1 and 40")
        resolved_key = api_key.strip() if api_key else None
        if min_request_interval_seconds is None:
            min_request_interval_seconds = (
                DEFAULT_AUTHENTICATED_MIN_REQUEST_INTERVAL_SECONDS
                if resolved_key
                else DEFAULT_ANONYMOUS_MIN_REQUEST_INTERVAL_SECONDS
            )
        if adaptive_max_interval_seconds is None:
            adaptive_max_interval_seconds = max(
                DEFAULT_ADAPTIVE_MAX_INTERVAL_SECONDS,
                min_request_interval_seconds,
            )
        if min_request_interval_seconds < 0:
            raise ValueError("min_request_interval_seconds must be >= 0")
        if max_retries_on_429 < 0:
            raise ValueError("max_retries_on_429 must be >= 0")
        if rate_limit_backoff_seconds <= 0:
            raise ValueError("rate_limit_backoff_seconds must be positive")
        if rate_limit_max_backoff_seconds < rate_limit_backoff_seconds:
            raise ValueError(
                "rate_limit_max_backoff_seconds must be >= "
                "rate_limit_backoff_seconds"
            )
        if rate_limit_circuit_breaker_threshold < 1:
            raise ValueError("rate_limit_circuit_breaker_threshold must be >= 1")
        if adaptive_max_interval_seconds < min_request_interval_seconds:
            raise ValueError(
                "adaptive_max_interval_seconds must be >= "
                "min_request_interval_seconds"
            )
        self._timeout_seconds = timeout_seconds
        self._max_results = max_results
        self._api_key = resolved_key
        self._fetch_json = fetch_json
        self._base_min_request_interval_seconds = min_request_interval_seconds
        self._min_request_interval_seconds = min_request_interval_seconds
        self._max_retries_on_429 = max_retries_on_429
        self._rate_limit_backoff_seconds = rate_limit_backoff_seconds
        self._rate_limit_max_backoff_seconds = rate_limit_max_backoff_seconds
        self._rate_limit_circuit_breaker_threshold = (
            rate_limit_circuit_breaker_threshold
        )
        self._adaptive_max_interval_seconds = adaptive_max_interval_seconds
        self._sleep = sleep or time.sleep
        self._last_request_monotonic: float | None = None
        self._consecutive_rate_limit_failures = 0
        self._rate_limit_circuit_open = False
        self._logged_request_mode = False
        self._fell_back_to_anonymous = False
        self._request_count = 0
        self._retry_count = 0
        self._rate_limit_response_count = 0

    @property
    def uses_authentication(self) -> bool:
        """Return True when the provider currently attaches an API key."""
        return bool(self._api_key)

    @property
    def request_count(self) -> int:
        """Number of live HTTP attempts (including retries)."""
        return self._request_count

    @property
    def retry_count(self) -> int:
        """Number of 429 retry sleeps performed."""
        return self._retry_count

    @property
    def rate_limit_response_count(self) -> int:
        """Number of HTTP 429 responses observed."""
        return self._rate_limit_response_count

    @property
    def min_request_interval_seconds(self) -> float:
        """Current pacing interval (may increase after rate limits)."""
        return self._min_request_interval_seconds

    def enrich(self, book: Book) -> BookEnrichmentResult:
        """Search Google Books and return the best enrichment match.

        Does not mutate ``book``.
        """
        title = book.title.strip()
        author = book.author.strip()
        if not title:
            return BookEnrichmentResult(
                isbn=book.isbn,
                status=BookEnrichmentStatus.ERROR,
                message="Cannot enrich a book with an empty title",
                metadata={"provider": "google_books"},
            )

        if self._rate_limit_circuit_open and self._fetch_json is None:
            return BookEnrichmentResult(
                isbn=book.isbn,
                status=BookEnrichmentStatus.ERROR,
                message=RATE_LIMIT_STOPPED_MESSAGE,
                metadata={
                    "provider": "google_books",
                    "error_kind": "rate_limit",
                    "circuit_open": True,
                },
            )

        queries = _build_queries(title, author)
        last_not_found_message = "No Google Books results"

        for query in queries:
            try:
                payload = self._search(query)
                candidates = _parse_volumes(payload)
            except GoogleBooksTransportError as exc:
                _logger.warning(
                    "Google Books enrich failed for isbn=%s query=%r: %s",
                    book.isbn,
                    query,
                    exc.message,
                )
                if exc.kind == "rate_limit":
                    self._record_rate_limit_failure()
                message = exc.message
                if exc.kind == "rate_limit":
                    message = RATE_LIMIT_USER_MESSAGE
                elif exc.kind == "auth":
                    message = AUTH_FAILURE_USER_MESSAGE
                return BookEnrichmentResult(
                    isbn=book.isbn,
                    status=BookEnrichmentStatus.ERROR,
                    message=message,
                    metadata={
                        "provider": "google_books",
                        "error_kind": exc.kind,
                        "query": query,
                    },
                )

            self._record_successful_request()
            if not candidates:
                last_not_found_message = "No Google Books results for query"
                continue

            scored = [_score_candidate(book, candidate) for candidate in candidates]
            status, match, message, peers = _select_match(scored)

            if status is BookEnrichmentStatus.NOT_FOUND:
                last_not_found_message = message
                continue

            return _result_from_candidate(
                book,
                status,
                match,
                message=message,
                query=query,
                ambiguous_peers=peers,
            )

        return BookEnrichmentResult(
            isbn=book.isbn,
            status=BookEnrichmentStatus.NOT_FOUND,
            message=last_not_found_message,
            metadata={"provider": "google_books"},
        )

    def _search(self, query: str) -> Mapping[str, Any]:
        """Execute one volumes search and return parsed JSON."""
        self._log_request_mode_once()
        url = self._build_search_url(query)
        # Log query only — never the full URL (may contain an API key).
        _logger.debug("Google Books search q=%r", query)

        if self._fetch_json is not None:
            return self._search_with_injected_fetcher(url, query)

        try:
            return self._fetch_json_with_rate_limits(url)
        except GoogleBooksTransportError as exc:
            if exc.kind != "auth" or not self._fallback_to_anonymous():
                raise
            anonymous_url = self._build_search_url(query)
            return self._fetch_json_with_rate_limits(anonymous_url)

    def _search_with_injected_fetcher(
        self,
        url: str,
        query: str,
    ) -> Mapping[str, Any]:
        """Run injectable fetch_json, with one anonymous retry on auth failure."""
        assert self._fetch_json is not None
        try:
            payload = self._invoke_injected_fetcher(url)
        except GoogleBooksTransportError as exc:
            if exc.kind != "auth" or not self._fallback_to_anonymous():
                raise
            payload = self._invoke_injected_fetcher(self._build_search_url(query))
        if not isinstance(payload, Mapping):
            raise GoogleBooksTransportError(
                "Google Books response JSON must be an object",
                kind="malformed",
            )
        return payload

    def _invoke_injected_fetcher(self, url: str) -> Mapping[str, Any]:
        assert self._fetch_json is not None
        try:
            payload = self._fetch_json(url)
        except GoogleBooksTransportError:
            raise
        except TimeoutError as exc:
            raise GoogleBooksTransportError(
                "Google Books request timed out",
                kind="timeout",
            ) from exc
        except Exception as exc:
            raise GoogleBooksTransportError(
                f"Google Books request failed: {exc}",
                kind="error",
            ) from exc
        return payload

    def _build_search_url(self, query: str) -> str:
        """Build a volumes search URL (includes key only while authenticated)."""
        params: dict[str, str | int] = {
            "q": query,
            "maxResults": self._max_results,
            "printType": "books",
        }
        if self._api_key:
            params["key"] = self._api_key
        return f"{GOOGLE_BOOKS_VOLUMES_URL}?{urlencode(params)}"

    def _log_request_mode_once(self) -> None:
        """Log Authenticated/Anonymous exactly once per provider instance."""
        if self._logged_request_mode:
            return
        self._logged_request_mode = True
        mode = "Authenticated" if self._api_key else "Anonymous"
        _logger.info("Google Books requests: %s", mode)

    def _fallback_to_anonymous(self) -> bool:
        """Drop a rejected API key and switch to anonymous pacing.

        Returns:
            True when a fallback was performed (caller should retry once).
        """
        if not self._api_key or self._fell_back_to_anonymous:
            return False
        self._api_key = None
        self._fell_back_to_anonymous = True
        self._base_min_request_interval_seconds = (
            DEFAULT_ANONYMOUS_MIN_REQUEST_INTERVAL_SECONDS
        )
        self._min_request_interval_seconds = (
            DEFAULT_ANONYMOUS_MIN_REQUEST_INTERVAL_SECONDS
        )
        self._adaptive_max_interval_seconds = max(
            self._adaptive_max_interval_seconds,
            DEFAULT_ANONYMOUS_MIN_REQUEST_INTERVAL_SECONDS,
        )
        _logger.warning(
            "Google Books API key rejected; switching to Anonymous for "
            "the remainder of this run"
        )
        # Allow a fresh mode log if enrichment continues after fallback.
        self._logged_request_mode = False
        self._log_request_mode_once()
        return True

    def _fetch_json_with_rate_limits(self, url: str) -> Mapping[str, Any]:
        """GET with pacing and exponential backoff on HTTP 429."""
        attempts = self._max_retries_on_429 + 1
        last_rate_limit: GoogleBooksTransportError | None = None
        for attempt in range(attempts):
            self._wait_for_request_slot()
            self._request_count += 1
            try:
                return _default_fetch_json(
                    url,
                    timeout_seconds=self._timeout_seconds,
                )
            except GoogleBooksTransportError as exc:
                if exc.kind == "rate_limit":
                    self._rate_limit_response_count += 1
                    last_rate_limit = exc
                    self._slow_down_after_rate_limit()
                    if attempt >= attempts - 1:
                        break
                    delay = self._rate_limit_delay(attempt, exc.retry_after_seconds)
                    _logger.warning(
                        "Google Books rate limited (429); retry %s/%s after %.1fs",
                        attempt + 1,
                        self._max_retries_on_429,
                        delay,
                    )
                    self._retry_count += 1
                    self._sleep(delay)
                    continue
                raise
        raise GoogleBooksTransportError(
            RATE_LIMIT_USER_MESSAGE,
            kind="rate_limit",
            retry_after_seconds=(
                last_rate_limit.retry_after_seconds
                if last_rate_limit is not None
                else None
            ),
        )

    def _rate_limit_delay(
        self,
        attempt: int,
        retry_after_seconds: float | None,
    ) -> float:
        """Choose backoff delay for a 429, honoring Retry-After when present."""
        exponential = min(
            self._rate_limit_backoff_seconds * (2**attempt),
            self._rate_limit_max_backoff_seconds,
        )
        if retry_after_seconds is None:
            return exponential
        return min(
            max(exponential, retry_after_seconds),
            self._rate_limit_max_backoff_seconds,
        )

    def _slow_down_after_rate_limit(self) -> None:
        """Increase pacing for the rest of the run after a 429."""
        if self._base_min_request_interval_seconds <= 0:
            return
        bumped = min(
            max(
                self._min_request_interval_seconds * 1.5,
                self._base_min_request_interval_seconds * 1.5,
            ),
            self._adaptive_max_interval_seconds,
        )
        if bumped > self._min_request_interval_seconds:
            _logger.info(
                "Slowing Google Books pacing to %.2fs after rate limit",
                bumped,
            )
            self._min_request_interval_seconds = bumped

    def _record_rate_limit_failure(self) -> None:
        """Track book-level rate-limit failures and open the circuit if needed."""
        self._consecutive_rate_limit_failures += 1
        if (
            self._consecutive_rate_limit_failures
            >= self._rate_limit_circuit_breaker_threshold
        ):
            self._rate_limit_circuit_open = True
            _logger.warning(
                "Opening Google Books rate-limit circuit after %s consecutive "
                "failures; remaining lookups will be skipped",
                self._consecutive_rate_limit_failures,
            )

    def _record_successful_request(self) -> None:
        """Reset consecutive rate-limit failure tracking after a good response."""
        self._consecutive_rate_limit_failures = 0

    def _wait_for_request_slot(self) -> None:
        """Sleep so consecutive live requests respect the minimum interval."""
        interval = self._min_request_interval_seconds
        if interval <= 0:
            self._last_request_monotonic = time.monotonic()
            return
        now = time.monotonic()
        if self._last_request_monotonic is not None:
            elapsed = now - self._last_request_monotonic
            remaining = interval - elapsed
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_monotonic = time.monotonic()
