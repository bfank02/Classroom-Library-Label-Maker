"""Interactive ISBN review workflow (UI-independent).

Teachers resolve ambiguous enrichment outcomes by choosing among preserved
:class:`~classroom_library_label_maker.models.ReviewCandidate` values or
skipping. No Google Books requests, workbook I/O, or Qt types belong here.

Typical flow::

    session = ReviewSession.from_pairs(list(zip(books, review_items, strict=True)))
    while not session.is_complete():
        item = session.current_item()
        # GUI presents item.candidates ...
        session.select_candidate(item.candidates[0])  # or skip_current()
        session.next()
    session.finish()
    result = BookReviewService().apply(session)
"""

from __future__ import annotations

from collections.abc import Sequence

from classroom_library_label_maker.models import (
    Book,
    EnrichmentSummary,
    ReviewCandidate,
    ReviewDecision,
    ReviewItem,
    ReviewSessionResult,
    WorkbookGenerationResult,
)


def review_session_from_generation_result(
    result: WorkbookGenerationResult,
) -> ReviewSession | None:
    """Build a :class:`ReviewSession` from enrichment review items that carry books.

    Returns ``None`` when there is nothing to review (no enrichment summary,
    empty queue, or items without attached ``book`` references).
    """
    return review_session_from_enrichment(result.enrichment)


def review_session_from_enrichment(
    summary: EnrichmentSummary | None,
) -> ReviewSession | None:
    """Build a :class:`ReviewSession` from an :class:`EnrichmentSummary`."""
    if summary is None or not summary.review_items:
        return None
    pairs = [
        (item.book, item)
        for item in summary.review_items
        if item.book is not None
    ]
    if not pairs:
        return None
    return ReviewSession.from_pairs(pairs)


class ReviewSession:
    """Stateful interactive review queue owned by the domain, not the GUI.

    Construct from parallel ``Book`` / ``ReviewItem`` pairs produced after
    enrichment. Navigation, decisions, and completion live on this object so
    adapters never keep their own indexes.
    """

    def __init__(
        self,
        books: Sequence[Book],
        items: Sequence[ReviewItem],
    ) -> None:
        if len(books) != len(items):
            raise ValueError(
                "books and review items must have the same length "
                f"(got {len(books)} books and {len(items)} items)"
            )
        self._books: tuple[Book, ...] = tuple(books)
        self._items: tuple[ReviewItem, ...] = tuple(items)
        self._index: int = 0
        self._decisions: dict[int, ReviewDecision] = {}
        self._finished: bool = False

    @classmethod
    def from_pairs(
        cls,
        pairs: Sequence[tuple[Book, ReviewItem]],
    ) -> ReviewSession:
        """Build a session from ``(book, review_item)`` pairs."""
        books = [book for book, _ in pairs]
        items = [item for _, item in pairs]
        return cls(books, items)

    def item_count(self) -> int:
        """Total entries in the review queue."""
        return len(self._items)

    def current_index(self) -> int:
        """Zero-based index of the current entry (``0`` when the queue is empty)."""
        return self._index

    def current_item(self) -> ReviewItem | None:
        """Review payload for the current entry, or ``None`` if the queue is empty."""
        if not self._items:
            return None
        return self._items[self._index]

    def current_book(self) -> Book | None:
        """Original book for the current entry, or ``None`` if the queue is empty."""
        if not self._books:
            return None
        return self._books[self._index]

    def remaining_count(self) -> int:
        """Number of queue entries that still lack a teacher decision."""
        return self.item_count() - len(self._decisions)

    def is_complete(self) -> bool:
        """True when every queue entry has a decision (or the queue is empty)."""
        return self.remaining_count() == 0

    def is_finished(self) -> bool:
        """True after :meth:`finish` seals the session against further edits."""
        return self._finished

    def has_decision_for_current(self) -> bool:
        """True when the current entry already has a recorded decision."""
        return self._index in self._decisions

    def decision_for_current(self) -> ReviewDecision | None:
        """Return the decision for the current entry, if any."""
        return self._decisions.get(self._index)

    def decisions(self) -> tuple[ReviewDecision, ...]:
        """Recorded decisions in queue order (undecided slots omitted)."""
        return tuple(
            self._decisions[index]
            for index in range(self.item_count())
            if index in self._decisions
        )

    def decision_at(self, index: int) -> ReviewDecision | None:
        """Return the decision at ``index``, or ``None`` if undecided."""
        if index < 0 or index >= self.item_count():
            raise IndexError("review index out of range")
        return self._decisions.get(index)

    def books(self) -> tuple[Book, ...]:
        """Original books in queue order."""
        return self._books

    def items(self) -> tuple[ReviewItem, ...]:
        """Review payloads in queue order."""
        return self._items

    def next(self) -> bool:
        """Advance to the next entry. Returns False when already at the end."""
        self._ensure_editable()
        if not self._items or self._index >= self.item_count() - 1:
            return False
        self._index += 1
        return True

    def previous(self) -> bool:
        """Move to the previous entry. Returns False when already at the start."""
        self._ensure_editable()
        if not self._items or self._index <= 0:
            return False
        self._index -= 1
        return True

    def select_candidate(self, candidate: ReviewCandidate) -> ReviewDecision:
        """Record a candidate choice for the current entry (replaces prior decision).

        Args:
            candidate: Must be one of ``current_item().candidates``.

        Returns:
            The recorded :class:`ReviewDecision`.

        Raises:
            RuntimeError: If the session is finished or the queue is empty.
            ValueError: If ``candidate`` is not an option for the current item,
                or it has no usable ISBN.
        """
        self._ensure_editable()
        book = self.current_book()
        item = self.current_item()
        if book is None or item is None:
            raise RuntimeError("review queue is empty")
        if candidate not in item.candidates:
            raise ValueError(
                "candidate is not among the preserved options for this item"
            )
        isbn = _candidate_isbn(candidate)
        if not isbn:
            raise ValueError("candidate has no usable ISBN")
        decision = ReviewDecision(book=book, candidate=candidate, skipped=False)
        self._decisions[self._index] = decision
        return decision

    def skip_current(self) -> ReviewDecision:
        """Record a skip for the current entry (book left unchanged)."""
        self._ensure_editable()
        book = self.current_book()
        if book is None:
            raise RuntimeError("review queue is empty")
        decision = ReviewDecision(book=book, candidate=None, skipped=True)
        self._decisions[self._index] = decision
        return decision

    def finish(self) -> None:
        """Seal the session. Further navigation or decisions raise."""
        if self._finished:
            return
        self._finished = True

    def _ensure_editable(self) -> None:
        if self._finished:
            raise RuntimeError("review session is finished")


class BookReviewService:
    """Apply completed :class:`ReviewSession` decisions to in-memory books.

    Does not write workbooks, call catalog providers, or depend on Qt.
    """

    def apply(self, session: ReviewSession) -> ReviewSessionResult:
        """Produce updated books and summary counts from a finished session.

        Args:
            session: Session that has been sealed with :meth:`ReviewSession.finish`.

        Returns:
            Immutable :class:`ReviewSessionResult`.

        Raises:
            RuntimeError: If ``session`` has not been finished.
        """
        if not session.is_finished():
            raise RuntimeError("review session must be finished before apply")

        updated: list[Book] = []
        resolved = 0
        skipped = 0
        unresolved = 0

        for index, book in enumerate(session.books()):
            decision = session.decision_at(index)
            if decision is None:
                updated.append(book)
                unresolved += 1
                continue
            if decision.skipped:
                updated.append(book)
                skipped += 1
                continue
            assert decision.candidate is not None
            updated.append(_book_with_selected_isbn(book, decision.candidate))
            resolved += 1

        return ReviewSessionResult(
            updated_books=tuple(updated),
            resolved_count=resolved,
            skipped_count=skipped,
            unresolved_count=unresolved,
            total_reviewed=resolved + skipped,
        )


def _candidate_isbn(candidate: ReviewCandidate) -> str:
    """Prefer ISBN-13, then ISBN-10."""
    for value in (candidate.isbn13, candidate.isbn10):
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _book_with_selected_isbn(book: Book, candidate: ReviewCandidate) -> Book:
    """Return a new book with the candidate ISBN; preserve all other fields."""
    isbn = _candidate_isbn(candidate)
    return Book(
        isbn=isbn,
        title=book.title,
        author=book.author,
        copies=book.copies,
        genre=book.genre,
        reading_level=book.reading_level,
        location=book.location,
        condition=book.condition,
    )
