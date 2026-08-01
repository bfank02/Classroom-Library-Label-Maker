"""Tests for ReviewCandidate preservation (Phase 4.1)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from classroom_library_label_maker.config import load_application_settings
from classroom_library_label_maker.constants import DEFAULT_LABEL_TEMPLATE_ID
from classroom_library_label_maker.models import (
    Book,
    BookEnrichmentResult,
    BookEnrichmentStatus,
    ReviewCandidate,
    ReviewItem,
)
from classroom_library_label_maker.services.book_enrichment_service import (
    BookEnrichmentService,
)
from classroom_library_label_maker.services.lookups.google_books import (
    GoogleBooksEnrichmentProvider,
)
from classroom_library_label_maker.services.workbook_generation_service import (
    WorkbookGenerationService,
)


def _volume(
    *,
    volume_id: str,
    title: str,
    authors: list[str],
    isbn13: str | None = None,
    isbn10: str | None = None,
    publisher: str | None = "Pub",
    published_date: str = "2001",
) -> dict[str, Any]:
    identifiers: list[dict[str, str]] = []
    if isbn13:
        identifiers.append({"type": "ISBN_13", "identifier": isbn13})
    if isbn10:
        identifiers.append({"type": "ISBN_10", "identifier": isbn10})
    volume_info: dict[str, Any] = {
        "title": title,
        "authors": authors,
        "publisher": publisher,
        "publishedDate": published_date,
    }
    if identifiers:
        volume_info["industryIdentifiers"] = identifiers
    return {"id": volume_id, "volumeInfo": volume_info}


def _payload(*volumes: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "books#volumes",
        "totalItems": len(volumes),
        "items": list(volumes),
    }


class _ScriptedFetcher:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.urls: list[str] = []

    def __call__(self, url: str) -> dict[str, Any]:
        self.urls.append(url)
        if not self.responses:
            raise AssertionError(f"Unexpected fetch: {url}")
        return self.responses.pop(0)


def test_review_candidate_is_immutable() -> None:
    candidate = ReviewCandidate(
        isbn13="9781111111111",
        title="Ocean Adventure",
        author="Pat Lee",
        confidence_score=0.9,
    )
    try:
        candidate.title = "Changed"  # type: ignore[misc]
        raised = False
    except FrozenInstanceError:
        raised = True
    assert raised


def test_found_result_has_empty_candidates() -> None:
    volumes = _payload(
        _volume(
            volume_id="cw",
            title="Charlotte's Web",
            authors=["E. B. White"],
            isbn13="9780064400558",
        )
    )
    book = Book(
        isbn="9780000000000",
        title="Charlotte's Web",
        author="E. B. White",
        copies=1,
    )
    result = GoogleBooksEnrichmentProvider(
        fetch_json=_ScriptedFetcher([volumes])
    ).enrich(book)
    assert result.status is BookEnrichmentStatus.FOUND
    assert result.candidates == ()


def test_ambiguous_preserves_ordered_candidates() -> None:
    """Ambiguous peers are kept, ordered by descending confidence."""
    volumes = _payload(
        _volume(
            volume_id="weak",
            title="Desert Adventure",
            authors=["Pat Lee"],
            isbn13="9782222222222",
            publisher="Desert Press",
            published_date="1999",
        ),
        _volume(
            volume_id="strong",
            title="Ocean Adventure",
            authors=["Pat Lee"],
            isbn13="9781111111111",
            isbn10="1111111111",
            publisher="Ocean Press",
            published_date="2005",
        ),
    )
    # Shared short title so both volumes score high and stay ambiguous.
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
    assert len(result.candidates) == 2
    confidences = [c.confidence_score for c in result.candidates]
    assert confidences == sorted(confidences, reverse=True)
    by_isbn = {c.isbn13: c for c in result.candidates}
    ocean = by_isbn["9781111111111"]
    assert ocean.isbn10 == "1111111111"
    assert ocean.title == "Ocean Adventure"
    assert ocean.author == "Pat Lee"
    assert ocean.publisher == "Ocean Press"
    assert ocean.published_date == "2005"
    desert = by_isbn["9782222222222"]
    assert desert.publisher == "Desert Press"
    assert desert.published_date == "1999"


def test_cached_ambiguous_result_skips_provider_and_keeps_candidates() -> None:
    """Review later reuses cached candidates — no second Google Books call."""
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
    fetcher = _ScriptedFetcher([volumes])
    service = BookEnrichmentService(
        provider=GoogleBooksEnrichmentProvider(fetch_json=fetcher)
    )
    book = Book(
        isbn="9780000000000",
        title="Adventure",
        author="Pat Lee",
        copies=1,
    )

    first = service.enrich(book)
    second = service.enrich(book)

    assert first.status is BookEnrichmentStatus.AMBIGUOUS
    assert len(first.candidates) == 2
    assert second is first or second == first
    assert second.candidates == first.candidates
    assert len(fetcher.urls) == 1
    assert service.cache_hits == 1
    assert service.cache_misses == 1


def test_generation_passes_candidates_onto_ambiguous_review_item(
    tmp_path: Path,
) -> None:
    candidates = (
        ReviewCandidate(
            isbn13="9781111111111",
            title="Ocean Adventure",
            author="Pat Lee",
            confidence_score=0.91,
        ),
        ReviewCandidate(
            isbn13="9782222222222",
            title="Desert Adventure",
            author="Pat Lee",
            confidence_score=0.88,
        ),
    )
    wb_path = tmp_path / "books.xlsx"
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Books"
    ws.append(["ISBN", "Title", "Author", "Copies"])
    ws.append(["", "Ambiguous Book", "A Author", 1])
    wb.save(wb_path)

    barcodes = tmp_path / "barcodes"
    barcodes.mkdir()
    settings = load_application_settings(
        workbook_path=wb_path,
        barcode_output_directory=barcodes,
        label_template_id=DEFAULT_LABEL_TEMPLATE_ID,
        overwrite=True,
        lookup_missing_isbns=True,
    )

    class _Provider:
        def enrich(self, book: Book) -> BookEnrichmentResult:
            return BookEnrichmentResult(
                isbn="x",
                status=BookEnrichmentStatus.AMBIGUOUS,
                message="two hits",
                candidates=candidates,
            )

    result = WorkbookGenerationService(
        settings,
        enrichment=BookEnrichmentService(provider=_Provider()),
    ).generate(workbook_path=wb_path, output_path=tmp_path / "out.xlsx")

    assert result.enrichment is not None
    assert len(result.enrichment.review_items) == 1
    item = result.enrichment.review_items[0]
    assert isinstance(item, ReviewItem)
    assert item.status is BookEnrichmentStatus.AMBIGUOUS
    assert item.candidates == candidates
    assert item.to_dict()["candidates"][0]["isbn13"] == "9781111111111"
