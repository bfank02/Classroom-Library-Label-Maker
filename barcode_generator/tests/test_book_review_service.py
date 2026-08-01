"""Unit tests for interactive review session and BookReviewService."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from classroom_library_label_maker.models import (
    Book,
    BookEnrichmentStatus,
    ReviewCandidate,
    ReviewDecision,
    ReviewItem,
    ReviewSessionResult,
)
from classroom_library_label_maker.services.book_review_service import (
    BookReviewService,
    ReviewSession,
)


def _book(
    title: str,
    *,
    isbn: str = "MISSING",
    author: str = "Author",
    copies: int = 1,
    genre: str | None = "Fiction",
) -> Book:
    return Book(
        isbn=isbn,
        title=title,
        author=author,
        copies=copies,
        genre=genre,
        reading_level="M",
        location="Bin A",
        condition="Good",
    )


def _candidate(
    isbn13: str,
    *,
    title: str = "Catalog Title",
    confidence_score: float = 0.9,
    isbn10: str | None = None,
) -> ReviewCandidate:
    return ReviewCandidate(
        isbn13=isbn13,
        isbn10=isbn10,
        title=title,
        author="Catalog Author",
        confidence_score=confidence_score,
    )


def _item(
    title: str,
    *,
    candidates: tuple[ReviewCandidate, ...] = (),
    status: BookEnrichmentStatus = BookEnrichmentStatus.AMBIGUOUS,
) -> ReviewItem:
    return ReviewItem(
        title=title,
        author="Author",
        status=status,
        message="Multiple catalog matches",
        candidates=candidates,
    )


def _session_with_two_books() -> tuple[ReviewSession, ReviewCandidate, ReviewCandidate]:
    c1a = _candidate("9781111111111", title="Ocean", confidence_score=0.91)
    c1b = _candidate("9782222222222", title="Desert", confidence_score=0.88)
    c2 = _candidate("9783333333333", title="Forest", confidence_score=0.87)
    session = ReviewSession.from_pairs(
        [
            (_book("Book One"), _item("Book One", candidates=(c1a, c1b))),
            (_book("Book Two"), _item("Book Two", candidates=(c2,))),
        ]
    )
    return session, c1a, c2


# --- ReviewDecision ----------------------------------------------------------


def test_review_decision_is_immutable() -> None:
    decision = ReviewDecision(
        book=_book("A"),
        candidate=_candidate("9781111111111"),
        skipped=False,
    )
    try:
        decision.skipped = True  # type: ignore[misc]
        raised = False
    except FrozenInstanceError:
        raised = True
    assert raised


def test_review_decision_rejects_invalid_combinations() -> None:
    book = _book("A")
    with pytest.raises(ValueError, match="require a candidate"):
        ReviewDecision(book=book, candidate=None, skipped=False)
    with pytest.raises(ValueError, match="must not include a candidate"):
        ReviewDecision(
            book=book,
            candidate=_candidate("9781111111111"),
            skipped=True,
        )


# --- Navigation --------------------------------------------------------------


def test_session_starts_at_first_item() -> None:
    session, c1a, _ = _session_with_two_books()
    assert session.item_count() == 2
    assert session.current_index() == 0
    assert session.current_item() is not None
    assert session.current_item().title == "Book One"
    assert session.current_book() is not None
    assert session.current_book().title == "Book One"
    assert session.remaining_count() == 2
    assert not session.is_complete()
    assert c1a in session.current_item().candidates


def test_next_and_previous_navigation() -> None:
    session, _, _ = _session_with_two_books()
    assert session.previous() is False
    assert session.current_index() == 0

    assert session.next() is True
    assert session.current_index() == 1
    assert session.current_item() is not None
    assert session.current_item().title == "Book Two"

    assert session.next() is False
    assert session.current_index() == 1

    assert session.previous() is True
    assert session.current_index() == 0


def test_empty_session_is_complete() -> None:
    session = ReviewSession([], [])
    assert session.item_count() == 0
    assert session.current_item() is None
    assert session.current_book() is None
    assert session.is_complete()
    assert session.remaining_count() == 0
    assert session.next() is False
    assert session.previous() is False


def test_mismatched_books_and_items_raise() -> None:
    with pytest.raises(ValueError, match="same length"):
        ReviewSession([_book("A")], [])


# --- Decisions ---------------------------------------------------------------


def test_select_candidate_records_decision() -> None:
    session, c1a, _ = _session_with_two_books()
    decision = session.select_candidate(c1a)
    assert decision.candidate == c1a
    assert not decision.skipped
    assert session.has_decision_for_current()
    assert session.remaining_count() == 1
    assert session.decision_for_current() == decision


def test_select_rejects_foreign_candidate() -> None:
    session, _, c2 = _session_with_two_books()
    with pytest.raises(ValueError, match="not among the preserved"):
        session.select_candidate(c2)


def test_select_rejects_candidate_without_isbn() -> None:
    bare = ReviewCandidate(title="No ISBN", confidence_score=0.9)
    session = ReviewSession.from_pairs(
        [(_book("A"), _item("A", candidates=(bare,)))]
    )
    with pytest.raises(ValueError, match="no usable ISBN"):
        session.select_candidate(bare)


def test_skip_current_records_skip() -> None:
    session, _, _ = _session_with_two_books()
    decision = session.skip_current()
    assert decision.skipped
    assert decision.candidate is None
    assert session.remaining_count() == 1


def test_select_replaces_prior_decision() -> None:
    session, c1a, _ = _session_with_two_books()
    c1b = session.current_item().candidates[1]  # type: ignore[union-attr]
    session.skip_current()
    session.select_candidate(c1a)
    assert session.decision_for_current() is not None
    assert session.decision_for_current().candidate == c1a
    session.select_candidate(c1b)
    assert session.decision_for_current().candidate == c1b
    assert session.remaining_count() == 1


def test_completion_when_all_decided() -> None:
    session, c1a, _ = _session_with_two_books()
    session.select_candidate(c1a)
    assert not session.is_complete()
    session.next()
    session.skip_current()
    assert session.is_complete()
    assert session.remaining_count() == 0
    assert len(session.decisions()) == 2


def test_finish_seals_session() -> None:
    session, c1a, _ = _session_with_two_books()
    session.select_candidate(c1a)
    session.finish()
    assert session.is_finished()
    with pytest.raises(RuntimeError, match="finished"):
        session.next()
    with pytest.raises(RuntimeError, match="finished"):
        session.skip_current()
    with pytest.raises(RuntimeError, match="finished"):
        session.select_candidate(c1a)


# --- BookReviewService -------------------------------------------------------


def test_apply_requires_finished_session() -> None:
    session, c1a, _ = _session_with_two_books()
    session.select_candidate(c1a)
    with pytest.raises(RuntimeError, match="finished"):
        BookReviewService().apply(session)


def test_apply_updates_selected_isbn_and_preserves_fields() -> None:
    c1a = _candidate("9781111111111", isbn10="1111111111")
    book = _book("Book One", copies=3, genre="Mystery")
    session = ReviewSession.from_pairs(
        [(book, _item("Book One", candidates=(c1a,)))]
    )
    session.select_candidate(c1a)
    session.finish()
    result = BookReviewService().apply(session)

    assert result.resolved_count == 1
    assert result.skipped_count == 0
    assert result.unresolved_count == 0
    assert result.total_reviewed == 1
    updated = result.updated_books[0]
    assert updated.isbn == "9781111111111"
    assert updated.title == "Book One"
    assert updated.author == "Author"
    assert updated.copies == 3
    assert updated.genre == "Mystery"
    assert updated.reading_level == "M"
    assert updated.location == "Bin A"
    assert updated.condition == "Good"
    assert updated is not book
    assert book.isbn == "MISSING"


def test_apply_prefers_isbn13_over_isbn10() -> None:
    candidate = _candidate("9781111111111", isbn10="1111111111")
    session = ReviewSession.from_pairs(
        [(_book("A"), _item("A", candidates=(candidate,)))]
    )
    session.select_candidate(candidate)
    session.finish()
    result = BookReviewService().apply(session)
    assert result.updated_books[0].isbn == "9781111111111"


def test_apply_uses_isbn10_when_isbn13_missing() -> None:
    candidate = ReviewCandidate(
        isbn13=None,
        isbn10="0064400557",
        title="Charlotte's Web",
        confidence_score=0.9,
    )
    session = ReviewSession.from_pairs(
        [(_book("A"), _item("A", candidates=(candidate,)))]
    )
    session.select_candidate(candidate)
    session.finish()
    result = BookReviewService().apply(session)
    assert result.updated_books[0].isbn == "0064400557"


def test_apply_skip_leaves_book_unchanged() -> None:
    book = _book("Book One")
    session = ReviewSession.from_pairs(
        [(book, _item("Book One", candidates=(_candidate("9781111111111"),)))]
    )
    session.skip_current()
    session.finish()
    result = BookReviewService().apply(session)
    assert result.skipped_count == 1
    assert result.resolved_count == 0
    assert result.updated_books[0] is book
    assert result.updated_books[0].isbn == "MISSING"


def test_apply_counts_unresolved() -> None:
    session, c1a, _ = _session_with_two_books()
    session.select_candidate(c1a)
    session.finish()
    result = BookReviewService().apply(session)
    assert result.resolved_count == 1
    assert result.skipped_count == 0
    assert result.unresolved_count == 1
    assert result.total_reviewed == 1
    assert result.updated_books[0].isbn == "9781111111111"
    assert result.updated_books[1].isbn == "MISSING"


def test_review_session_result_is_immutable_and_serializable() -> None:
    result = ReviewSessionResult(
        updated_books=(_book("A", isbn="9781111111111"),),
        resolved_count=1,
        skipped_count=0,
        unresolved_count=0,
        total_reviewed=1,
    )
    try:
        result.resolved_count = 9  # type: ignore[misc]
        raised = False
    except FrozenInstanceError:
        raised = True
    assert raised
    payload = result.to_dict()
    assert payload["resolved_count"] == 1
    assert payload["updated_books"][0]["isbn"] == "9781111111111"
