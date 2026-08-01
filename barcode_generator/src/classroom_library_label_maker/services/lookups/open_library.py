"""Open Library catalog enrichment provider.

Implements
:class:`~classroom_library_label_maker.services.protocols.BookEnrichmentProvider`
using the public Open Library Search API. HTTP and Open Library response shapes
stay inside this module — callers only see :class:`BookEnrichmentResult`.

Used as a secondary catalog behind Google Books via
:class:`~classroom_library_label_maker.services.lookups.composite.CompositeBookEnrichmentProvider`.

Matching reuses the public title/author confidence helpers from
:mod:`google_books` (same thresholds and ambiguity philosophy). Shared
extraction can wait until a third provider makes the duplication real.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import json
import logging
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
from classroom_library_label_maker.services.lookups.google_books import (
    author_similarity,
    combined_confidence,
    title_similarity,
)

_logger = get_logger("open_library")

OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_RESULTS = 10
DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = 0.25

# Keep aligned with google_books until shared matching extraction is justified.
_FOUND_THRESHOLD = 0.85
_CONSIDER_THRESHOLD = 0.72
_AMBIGUOUS_MARGIN = 0.06
_EDITION_TITLE_THRESHOLD = 0.92
_EDITION_AUTHOR_THRESHOLD = 0.80

_WHITESPACE_RE = re.compile(r"\s+")
_ISBN13_RE = re.compile(r"^(978|979)\d{10}$")
_ISBN10_RE = re.compile(r"^\d{9}[\dXx]$")

JsonFetcher = Callable[[str], Mapping[str, Any]]

__all__ = [
    "DEFAULT_MAX_RESULTS",
    "DEFAULT_MIN_REQUEST_INTERVAL_SECONDS",
    "DEFAULT_TIMEOUT_SECONDS",
    "OPEN_LIBRARY_SEARCH_URL",
    "OpenLibraryEnrichmentProvider",
    "OpenLibraryTransportError",
    "JsonFetcher",
]


class OpenLibraryTransportError(Exception):
    """Internal transport / parse failure; never raised out of ``enrich``."""

    def __init__(self, message: str, *, kind: str = "error") -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message


@dataclass(frozen=True, slots=True)
class _EditionCandidate:
    """Provider-local Open Library candidate (not part of the public API)."""

    title: str
    authors: tuple[str, ...]
    isbn13: str | None
    isbn10: str | None
    publisher: str | None
    publish_year: str | None
    work_key: str


@dataclass(frozen=True, slots=True)
class _ScoredCandidate:
    """Candidate plus confidence against the query book."""

    candidate: _EditionCandidate
    title_score: float
    author_score: float
    confidence: float


def _default_fetch_json(url: str, *, timeout_seconds: float) -> Mapping[str, Any]:
    """GET ``url`` with urllib and return parsed JSON."""
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": f"{APP_NAME}/{APP_VERSION} (classroom library labels)",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read()
    except TimeoutError as exc:
        raise OpenLibraryTransportError(
            "Open Library request timed out",
            kind="timeout",
        ) from exc
    except HTTPError as exc:
        raise OpenLibraryTransportError(
            f"Open Library HTTP error: {exc.code}",
            kind="http",
        ) from exc
    except URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
            raise OpenLibraryTransportError(
                "Open Library request timed out",
                kind="timeout",
            ) from exc
        raise OpenLibraryTransportError(
            f"Open Library network error: {reason}",
            kind="network",
        ) from exc
    except OSError as exc:
        raise OpenLibraryTransportError(
            f"Open Library network error: {exc}",
            kind="network",
        ) from exc

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OpenLibraryTransportError(
            "Open Library response was not valid JSON",
            kind="malformed",
        ) from exc

    if not isinstance(payload, dict):
        raise OpenLibraryTransportError(
            "Open Library response JSON must be an object",
            kind="malformed",
        )
    return payload


def _build_search_plans(title: str, author: str) -> tuple[tuple[str, dict[str, str]], ...]:
    """Return ordered ``(label, query-params)`` plans (no author-only search)."""
    title = title.strip()
    author = author.strip()
    plans: list[tuple[str, dict[str, str]]] = []
    if title and author:
        plans.append(
            (
                f"title={title!r} author={author!r}",
                {"title": title, "author": author},
            )
        )
    if title:
        plans.append((f"title={title!r}", {"title": title}))
    return tuple(plans)


def _normalize_isbn_token(raw: str) -> str:
    return raw.replace("-", "").replace(" ", "").strip()


def _pick_isbns(raw_isbns: Sequence[Any] | None) -> tuple[str | None, str | None]:
    """Return ``(isbn13, isbn10)`` preferring ISBN-13."""
    if not raw_isbns:
        return None, None
    isbn13: str | None = None
    isbn10: str | None = None
    for item in raw_isbns:
        value = _normalize_isbn_token(str(item))
        if not value:
            continue
        if isbn13 is None and _ISBN13_RE.match(value):
            isbn13 = value
        elif isbn10 is None and _ISBN10_RE.match(value):
            isbn10 = value.upper() if value[-1] in "xX" else value
        if isbn13 and isbn10:
            break
    return isbn13, isbn10


def _first_string(values: Any) -> str | None:
    if isinstance(values, str):
        text = values.strip()
        return text or None
    if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
        for item in values:
            text = str(item).strip()
            if text:
                return text
    return None


def _parse_doc(doc: Mapping[str, Any]) -> _EditionCandidate | None:
    """Map one Open Library search doc to an internal candidate."""
    raw_title = str(doc.get("title") or "").strip()
    if not raw_title:
        return None
    authors_raw = doc.get("author_name") or []
    authors: list[str] = []
    if isinstance(authors_raw, Sequence) and not isinstance(authors_raw, (str, bytes)):
        for author in authors_raw:
            text = str(author).strip()
            if text:
                authors.append(text)
    isbn13, isbn10 = _pick_isbns(doc.get("isbn"))
    year = doc.get("first_publish_year")
    publish_year = str(year).strip() if year is not None and str(year).strip() else None
    work_key = str(doc.get("key") or "").strip()
    return _EditionCandidate(
        title=_WHITESPACE_RE.sub(" ", raw_title).strip(),
        authors=tuple(authors),
        isbn13=isbn13,
        isbn10=isbn10,
        publisher=_first_string(doc.get("publisher")),
        publish_year=publish_year,
        work_key=work_key,
    )


def _parse_docs(payload: Mapping[str, Any]) -> list[_EditionCandidate]:
    docs = payload.get("docs")
    if docs is None:
        return []
    if not isinstance(docs, list):
        raise OpenLibraryTransportError(
            "Open Library response 'docs' must be a list",
            kind="malformed",
        )
    candidates: list[_EditionCandidate] = []
    for doc in docs:
        if isinstance(doc, Mapping):
            parsed = _parse_doc(doc)
            if parsed is not None:
                candidates.append(parsed)
    return candidates


def _score_candidate(book: Book, candidate: _EditionCandidate) -> _ScoredCandidate:
    title_score = title_similarity(book.title, candidate.title)
    author_score = author_similarity(book.author, candidate.authors)
    return _ScoredCandidate(
        candidate=candidate,
        title_score=title_score,
        author_score=author_score,
        confidence=combined_confidence(title_score, author_score),
    )


def _has_usable_isbn(candidate: _EditionCandidate | None) -> bool:
    if candidate is None:
        return False
    return bool(candidate.isbn13 or candidate.isbn10)


def _same_work(left: _ScoredCandidate, right: _ScoredCandidate) -> bool:
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
    """Choose FOUND / AMBIGUOUS / NOT_FOUND (same philosophy as Google Books)."""
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
    candidate = scored.candidate
    return ReviewCandidate(
        isbn13=candidate.isbn13,
        isbn10=candidate.isbn10,
        title=candidate.title,
        author=_format_authors(candidate.authors) or "",
        publisher=candidate.publisher,
        published_date=candidate.publish_year,
        confidence_score=round(scored.confidence, 4),
    )


def _format_debug_candidates(scored: Sequence[_ScoredCandidate], *, limit: int = 3) -> str:
    top = sorted(scored, key=lambda item: item.confidence, reverse=True)[:limit]
    if not top:
        return "  (none)"
    lines: list[str] = []
    for item in top:
        isbn = item.candidate.isbn13 or item.candidate.isbn10 or "(none)"
        lines.append(
            f"  - {item.candidate.title!r} "
            f"conf={item.confidence:.3f} isbn={isbn}"
        )
    return "\n".join(lines)


def _result_from_candidate(
    book: Book,
    status: BookEnrichmentStatus,
    scored: _ScoredCandidate | None,
    *,
    message: str,
    query: str | None = None,
    ambiguous_peers: Sequence[_ScoredCandidate] = (),
) -> BookEnrichmentResult:
    review_candidates: tuple[ReviewCandidate, ...] = ()
    if status is BookEnrichmentStatus.AMBIGUOUS and ambiguous_peers:
        review_candidates = tuple(
            _to_review_candidate(peer) for peer in ambiguous_peers
        )

    provider_name = OpenLibraryEnrichmentProvider.provider_name
    if scored is None:
        return BookEnrichmentResult(
            isbn=book.isbn,
            status=status,
            message=message,
            metadata={"provider": "open_library", "query": query},
            candidates=review_candidates,
            provider_name=provider_name,
        )

    candidate = scored.candidate
    resolved_isbn = candidate.isbn13 or candidate.isbn10 or book.isbn
    return BookEnrichmentResult(
        isbn=resolved_isbn,
        status=status,
        title=candidate.title,
        author=_format_authors(candidate.authors),
        message=message,
        metadata={
            "provider": "open_library",
            "isbn13": candidate.isbn13,
            "isbn10": candidate.isbn10,
            "authors": list(candidate.authors),
            "normalized_title": normalize_catalog_text(candidate.title),
            "normalized_author": normalize_catalog_text(
                _format_authors(candidate.authors) or ""
            ),
            "open_library_key": candidate.work_key or None,
            "publisher": candidate.publisher,
            "publish_year": candidate.publish_year,
            "confidence": round(scored.confidence, 4),
            "title_score": round(scored.title_score, 4),
            "author_score": round(scored.author_score, 4),
            "query": query,
            "source_isbn": book.isbn,
        },
        candidates=review_candidates,
        provider_name=provider_name,
    )


class OpenLibraryEnrichmentProvider:
    """Enrich books via Open Library title/author search.

    Search order (sequential; no author-only searches):

    1. ``title`` + ``author`` field search
    2. ``title``-only fallback

    A confident metadata match without a usable ISBN does not stop the search.
    Transport failures become :attr:`BookEnrichmentStatus.ERROR`.
    """

    provider_name = "Open Library"

    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_results: int = DEFAULT_MAX_RESULTS,
        fetch_json: JsonFetcher | None = None,
        min_request_interval_seconds: float = DEFAULT_MIN_REQUEST_INTERVAL_SECONDS,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not 1 <= max_results <= 100:
            raise ValueError("max_results must be between 1 and 100")
        if min_request_interval_seconds < 0:
            raise ValueError("min_request_interval_seconds must be >= 0")
        self._timeout_seconds = timeout_seconds
        self._max_results = max_results
        self._fetch_json = fetch_json
        self._min_request_interval_seconds = min_request_interval_seconds
        self._sleep = sleep or time.sleep
        self._last_request_monotonic: float | None = None
        self._request_count = 0

    @property
    def request_count(self) -> int:
        """Number of live HTTP attempts."""
        return self._request_count

    @property
    def min_request_interval_seconds(self) -> float:
        return self._min_request_interval_seconds

    def enrich(self, book: Book) -> BookEnrichmentResult:
        """Search Open Library and return the best enrichment match."""
        title = book.title.strip()
        author = book.author.strip()
        if not title:
            return BookEnrichmentResult(
                isbn=book.isbn,
                status=BookEnrichmentStatus.ERROR,
                message="Cannot enrich a book with an empty title",
                metadata={"provider": "open_library"},
                provider_name=self.provider_name,
            )

        plans = _build_search_plans(title, author)
        last_not_found_message = "No Open Library results"

        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(
                "Open Library Lookup\nBook:\n%s\n%s",
                title,
                author or "(no author)",
            )

        for index, (query_label, params) in enumerate(plans, start=1):
            try:
                payload = self._search(params)
                candidates = _parse_docs(payload)
            except OpenLibraryTransportError as exc:
                _logger.warning(
                    "Open Library enrich failed for isbn=%s query=%s: %s",
                    book.isbn,
                    query_label,
                    exc.message,
                )
                if _logger.isEnabledFor(logging.DEBUG):
                    _logger.debug(
                        "Query %s/%s\n%s\nFinal decision: error (%s)",
                        index,
                        len(plans),
                        query_label,
                        exc.message,
                    )
                return BookEnrichmentResult(
                    isbn=book.isbn,
                    status=BookEnrichmentStatus.ERROR,
                    message=exc.message,
                    metadata={
                        "provider": "open_library",
                        "error_kind": exc.kind,
                        "query": query_label,
                    },
                    provider_name=self.provider_name,
                )

            if not candidates:
                last_not_found_message = "No Open Library results for query"
                if _logger.isEnabledFor(logging.DEBUG):
                    _logger.debug(
                        "Query %s/%s\n%s\nCandidate count: 0\n"
                        "Rejected: empty result set\nContinuing...",
                        index,
                        len(plans),
                        query_label,
                    )
                continue

            scored = [_score_candidate(book, candidate) for candidate in candidates]
            status, match, message, peers = _select_match(scored)

            if status is BookEnrichmentStatus.NOT_FOUND:
                last_not_found_message = message
                if _logger.isEnabledFor(logging.DEBUG):
                    _logger.debug(
                        "Query %s/%s\n%s\nCandidate count: %s\n"
                        "Top candidates:\n%s\nRejected: %s\nContinuing...",
                        index,
                        len(plans),
                        query_label,
                        len(candidates),
                        _format_debug_candidates(scored),
                        message,
                    )
                continue

            if status is BookEnrichmentStatus.FOUND:
                usable = _has_usable_isbn(
                    match.candidate if match is not None else None
                )
                if not usable:
                    last_not_found_message = (
                        "Matching catalog record had no usable ISBN"
                    )
                    if _logger.isEnabledFor(logging.DEBUG):
                        _logger.debug(
                            "Query %s/%s\n%s\nCandidate count: %s\n"
                            "Top candidates:\n%s\n"
                            "Rejected: metadata match without usable ISBN\n"
                            "Continuing...",
                            index,
                            len(plans),
                            query_label,
                            len(candidates),
                            _format_debug_candidates(scored),
                        )
                    continue
                if _logger.isEnabledFor(logging.DEBUG):
                    _logger.debug(
                        "Query %s/%s\n%s\nCandidate count: %s\n"
                        "Top candidates:\n%s\nAccepted: usable ISBN\n"
                        "Final decision: found",
                        index,
                        len(plans),
                        query_label,
                        len(candidates),
                        _format_debug_candidates(scored),
                    )
                return _result_from_candidate(
                    book,
                    status,
                    match,
                    message=message,
                    query=query_label,
                    ambiguous_peers=peers,
                )

            # AMBIGUOUS
            usable_peers = tuple(
                peer for peer in peers if _has_usable_isbn(peer.candidate)
            )
            if not usable_peers:
                last_not_found_message = (
                    "Ambiguous catalog matches had no usable ISBN"
                )
                if _logger.isEnabledFor(logging.DEBUG):
                    _logger.debug(
                        "Query %s/%s\n%s\nCandidate count: %s\n"
                        "Rejected: ambiguous without usable ISBN\nContinuing...",
                        index,
                        len(plans),
                        query_label,
                        len(candidates),
                    )
                continue
            if _logger.isEnabledFor(logging.DEBUG):
                _logger.debug(
                    "Query %s/%s\n%s\nCandidate count: %s\n"
                    "Top candidates:\n%s\nAccepted: ambiguous with usable ISBN\n"
                    "Final decision: ambiguous",
                    index,
                    len(plans),
                    query_label,
                    len(candidates),
                    _format_debug_candidates(scored),
                )
            return _result_from_candidate(
                book,
                status,
                match,
                message=message,
                query=query_label,
                ambiguous_peers=usable_peers,
            )

        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(
                "Open Library final decision: not_found (%s)",
                last_not_found_message,
            )
        return BookEnrichmentResult(
            isbn=book.isbn,
            status=BookEnrichmentStatus.NOT_FOUND,
            message=last_not_found_message,
            metadata={"provider": "open_library"},
            provider_name=self.provider_name,
        )

    def _search(self, params: Mapping[str, str]) -> Mapping[str, Any]:
        """Execute one search and return parsed JSON."""
        query = {
            **params,
            "limit": str(self._max_results),
            "fields": (
                "key,title,author_name,isbn,publisher,first_publish_year"
            ),
        }
        url = f"{OPEN_LIBRARY_SEARCH_URL}?{urlencode(query)}"
        _logger.debug("Open Library search params=%r", dict(params))

        if self._fetch_json is not None:
            self._request_count += 1
            payload = self._fetch_json(url)
            if not isinstance(payload, Mapping):
                raise OpenLibraryTransportError(
                    "Open Library response JSON must be an object",
                    kind="malformed",
                )
            return payload

        self._pace()
        self._request_count += 1
        return _default_fetch_json(url, timeout_seconds=self._timeout_seconds)

    def _pace(self) -> None:
        if self._min_request_interval_seconds <= 0:
            self._last_request_monotonic = time.monotonic()
            return
        now = time.monotonic()
        if self._last_request_monotonic is not None:
            elapsed = now - self._last_request_monotonic
            remaining = self._min_request_interval_seconds - elapsed
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_monotonic = time.monotonic()
