"""Presentation tests for Review Wizard polish (v1.4 Phase 4)."""

from __future__ import annotations

import os

from PySide6.QtWidgets import QApplication, QLabel
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from classroom_library_label_maker.gui.app import create_application
from classroom_library_label_maker.gui.review_wizard import (
    ReviewWizardDialog,
    friendly_review_reason,
)
from classroom_library_label_maker.models import (
    Book,
    BookEnrichmentStatus,
    ReviewCandidate,
    ReviewItem,
)
from classroom_library_label_maker.services.book_review_service import ReviewSession


@pytest.fixture(scope="module")
def qapp():
    app = create_application(["classroom-library-label-maker-gui-review-polish"])
    yield app


def _book(title: str) -> Book:
    return Book(isbn="MISSING", title=title, author="Author", copies=1)


def _candidate(
    isbn13: str,
    *,
    title: str = "Catalog Title",
    confidence_score: float = 0.91,
) -> ReviewCandidate:
    return ReviewCandidate(
        isbn13=isbn13,
        title=title,
        author="Catalog Author",
        publisher="Pub",
        published_date="2005-01-01",
        confidence_score=confidence_score,
    )


def _item(
    book: Book,
    candidates: tuple[ReviewCandidate, ...],
    *,
    status: BookEnrichmentStatus = BookEnrichmentStatus.AMBIGUOUS,
    message: str = "Multiple catalog matches",
) -> ReviewItem:
    return ReviewItem(
        title=book.title,
        author=book.author,
        status=status,
        message=message,
        candidates=candidates,
        book=book,
    )


def _two_book_session() -> tuple[ReviewSession, ReviewCandidate, ReviewCandidate]:
    c1a = _candidate("9781111111111", title="Ocean", confidence_score=0.92)
    c1b = _candidate("9782222222222", title="Desert", confidence_score=0.88)
    c2 = _candidate("9783333333333", title="Forest", confidence_score=0.86)
    book1 = _book("Book One")
    book2 = _book("Book Two")
    session = ReviewSession.from_pairs(
        [
            (book1, _item(book1, (c1a, c1b))),
            (book2, _item(book2, (c2,), message="Needs review")),
        ]
    )
    return session, c1a, c2


def test_friendly_review_reason_ambiguous() -> None:
    book = _book("Book")
    item = _item(book, (_candidate("9781111111111"),))
    text = friendly_review_reason(item)
    assert "multiple matching editions" in text.lower()
    assert "choose the one that matches" in text.lower()


def test_layout_sections_constructed(qapp) -> None:
    session, _, _ = _two_book_session()
    dialog = ReviewWizardDialog(session)
    dialog.show()
    QApplication.processEvents()

    assert dialog.section_title_label.text() == "Review ISBN Matches"
    assert dialog.progress_label.text() == "Book 1 of 2"
    assert dialog.remaining_label.text() == "2 Remaining"
    assert dialog.findChild(object, "reviewProgressSection") is not None
    assert dialog.findChild(object, "reviewBookSection") is not None
    assert dialog.findChild(object, "reviewCandidatesSection") is not None
    assert dialog.candidates_caption.text() == "Choose a catalog match"
    assert "multiple matching editions" in dialog.reason_label.text().lower()
    assert "b45309" in dialog.reason_label.styleSheet()
    dialog.close()


def test_recommended_badge_wording_and_confidence(qapp) -> None:
    session, c1a, _ = _two_book_session()
    dialog = ReviewWizardDialog(session)
    dialog.show()
    QApplication.processEvents()

    card = dialog._cards[0]
    assert card.is_recommended() is True
    badge = card.findChild(QLabel, "reviewRecommendedBadge")
    confidence = card.findChild(QLabel, "reviewConfidenceBadge")
    assert badge is not None
    assert badge.text() == "⭐ Recommended Match"
    assert confidence is not None
    assert confidence.text() == "Very High Match"
    assert dialog._cards[1].findChild(QLabel, "reviewRecommendedBadge") is None
    assert card.candidate == c1a
    dialog.close()


def test_selected_styling_border_and_checkmark(qapp) -> None:
    session, c1a, _ = _two_book_session()
    dialog = ReviewWizardDialog(session, auto_advance_ms=250)
    dialog.show()
    QApplication.processEvents()

    card = dialog._cards[0]
    card.clicked.emit(c1a)
    QApplication.processEvents()

    assert card.property("selected") is True
    style = card.styleSheet()
    assert "3px solid" in style
    assert "#1d6fa5" in style or "#e3f2fb" in style
    assert card.check_label.isVisible() is True
    assert card.accessibleDescription() == "Selected"
    assert dialog._cards[1].property("selected") is not True
    dialog.close()


def test_skipped_state_presentation(qapp) -> None:
    session, _, _ = _two_book_session()
    dialog = ReviewWizardDialog(session, auto_advance_ms=5_000)
    dialog.show()
    QApplication.processEvents()

    dialog.skip_button.click()
    QApplication.processEvents()

    assert dialog.decision_status_label.text() == "✓ Label will not be generated"
    assert dialog.decision_status_label.isVisible() is True
    assert "#e8f5ee" in dialog.decision_status_label.styleSheet()
    assert all(card.property("selected") is not True for card in dialog._cards)
    assert dialog._advance_timer.isActive() is True

    dialog._cards[0].clicked.emit(dialog._cards[0].candidate)
    QApplication.processEvents()
    # Keep auto-advance pending so we stay on this book for the assertion.
    assert dialog._advance_timer.isActive() is True
    assert dialog.decision_status_label.text() == "Selected"
    assert "Label will not be generated" not in dialog.decision_status_label.text()
    assert dialog._cards[0].property("selected") is True
    dialog.close()


def test_accessibility_names_preserved(qapp) -> None:
    session, _, _ = _two_book_session()
    dialog = ReviewWizardDialog(session)
    dialog.show()
    QApplication.processEvents()

    assert dialog.accessibleName() == "Review ISBN Matches"
    assert dialog.progress_label.accessibleName() == "Review progress"
    assert dialog.remaining_label.accessibleName() == "Books remaining"
    assert dialog.reason_label.accessibleName() == "Review guidance"
    assert dialog.decision_status_label.accessibleName() == "Review decision status"
    assert dialog.previous_button.accessibleName() == "Previous"
    assert dialog.skip_button.accessibleName() == "Don't Generate Label"
    assert dialog.cancel_button.accessibleName() == "Cancel"
    assert "Recommended Match" in dialog._cards[0].accessibleName()
    dialog.close()
