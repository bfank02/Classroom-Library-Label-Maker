"""Workflow tests for streamlined Review Wizard auto-advance (v1.4 Phase 2)."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from classroom_library_label_maker.gui.app import create_application
from classroom_library_label_maker.gui.review_wizard import ReviewWizardDialog
from classroom_library_label_maker.models import (
    Book,
    BookEnrichmentStatus,
    ReviewCandidate,
    ReviewItem,
)
from classroom_library_label_maker.services.book_review_service import ReviewSession


@pytest.fixture(scope="module")
def qapp():
    app = create_application(["classroom-library-label-maker-gui-review-workflow"])
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
) -> ReviewItem:
    return ReviewItem(
        title=book.title,
        author=book.author,
        status=BookEnrichmentStatus.AMBIGUOUS,
        message="Multiple catalog matches",
        candidates=candidates,
        book=book,
    )


def _three_book_session() -> tuple[
    ReviewSession,
    ReviewCandidate,
    ReviewCandidate,
    ReviewCandidate,
]:
    c1a = _candidate("9781111111111", title="Ocean", confidence_score=0.92)
    c1b = _candidate("9782222222222", title="Desert", confidence_score=0.88)
    c2 = _candidate("9783333333333", title="Forest", confidence_score=0.86)
    c3 = _candidate("9784444444444", title="River", confidence_score=0.84)
    book1 = _book("Book One")
    book2 = _book("Book Two")
    book3 = _book("Book Three")
    session = ReviewSession.from_pairs(
        [
            (book1, _item(book1, (c1a, c1b))),
            (book2, _item(book2, (c2,))),
            (book3, _item(book3, (c3,))),
        ]
    )
    return session, c1a, c1b, c2


def _wait_advance(dialog: ReviewWizardDialog) -> None:
    """Process events until the auto-advance timer is idle."""
    for _ in range(50):
        QApplication.processEvents()
        if not dialog._advance_timer.isActive():
            QApplication.processEvents()
            return
        dialog._advance_timer.timeout.emit()
        QApplication.processEvents()
        return


def test_skip_auto_advances_immediately(qapp) -> None:
    session, _, _, _ = _three_book_session()
    dialog = ReviewWizardDialog(session, auto_advance_ms=250)
    dialog.show()
    QApplication.processEvents()

    dialog.skip_button.click()
    QApplication.processEvents()

    assert session.current_index() == 1
    assert session.decision_at(0) is not None
    assert session.decision_at(0).skipped is True
    assert dialog.progress_label.text() == "Book 2 of 3"
    assert dialog._advance_timer.isActive() is False
    dialog.close()


def test_selection_auto_advances_after_timer(qapp) -> None:
    session, c1a, _, _ = _three_book_session()
    dialog = ReviewWizardDialog(session, auto_advance_ms=250)
    dialog.show()
    QApplication.processEvents()

    dialog._cards[0].clicked.emit(c1a)
    QApplication.processEvents()

    assert session.current_index() == 0
    assert session.decision_for_current().candidate == c1a
    assert dialog._cards[0].property("selected") is True
    assert dialog._cards[0].check_label.isVisible() is True
    assert dialog._advance_timer.isActive() is True

    _wait_advance(dialog)

    assert session.current_index() == 1
    assert dialog.progress_label.text() == "Book 2 of 3"
    dialog.close()


def test_reselection_restarts_timer_and_uses_latest(qapp) -> None:
    session, c1a, c1b, _ = _three_book_session()
    dialog = ReviewWizardDialog(session, auto_advance_ms=250)
    dialog.show()
    QApplication.processEvents()

    dialog._cards[0].clicked.emit(c1a)
    QApplication.processEvents()
    assert dialog._advance_timer.isActive() is True

    dialog._cards[1].clicked.emit(c1b)
    QApplication.processEvents()
    assert session.decision_for_current().candidate == c1b
    assert dialog._cards[1].property("selected") is True
    assert dialog._cards[0].property("selected") is False
    assert dialog._advance_timer.isActive() is True

    _wait_advance(dialog)

    assert session.current_index() == 1
    assert session.decision_at(0).candidate == c1b
    dialog.close()


def test_previous_restores_skipped_state(qapp) -> None:
    session, _, _, _ = _three_book_session()
    dialog = ReviewWizardDialog(session, auto_advance_ms=0)
    dialog.show()
    QApplication.processEvents()

    dialog.skip_button.click()
    QApplication.processEvents()
    assert session.current_index() == 1

    dialog.previous_button.click()
    QApplication.processEvents()

    assert session.current_index() == 0
    assert session.decision_for_current().skipped is True
    assert all(card.property("selected") is not True for card in dialog._cards)
    assert dialog.decision_status_label.text() == "This book will be skipped."
    dialog.close()


def test_previous_restores_selected_candidate(qapp) -> None:
    session, c1a, _, _ = _three_book_session()
    dialog = ReviewWizardDialog(session, auto_advance_ms=0)
    dialog.show()
    QApplication.processEvents()

    dialog._cards[0].clicked.emit(c1a)
    QApplication.processEvents()
    assert session.current_index() == 1

    dialog.previous_button.click()
    QApplication.processEvents()

    assert session.current_index() == 0
    assert session.decision_for_current().candidate == c1a
    assert dialog._cards[0].property("selected") is True
    assert dialog._cards[0].check_label.isVisible() is True
    assert dialog.decision_status_label.text() == "Selected"
    dialog.close()


def test_final_finish_review_after_selection(qapp) -> None:
    c1 = _candidate("9781111111111", confidence_score=0.92)
    c2 = _candidate("9782222222222", confidence_score=0.88)
    book1 = _book("Book One")
    book2 = _book("Book Two")
    session = ReviewSession.from_pairs(
        [
            (book1, _item(book1, (c1,))),
            (book2, _item(book2, (c2,))),
        ]
    )
    dialog = ReviewWizardDialog(session, auto_advance_ms=0)
    dialog.show()
    QApplication.processEvents()

    assert dialog.finish_button.isVisible() is False
    dialog._cards[0].clicked.emit(c1)
    QApplication.processEvents()
    assert dialog.progress_label.text() == "Book 2 of 2"
    assert dialog.finish_button.isVisible() is False
    assert dialog.skip_button.isVisible() is True

    dialog._cards[0].clicked.emit(c2)
    QApplication.processEvents()
    assert dialog.finish_button.isVisible() is True
    assert dialog.skip_button.isVisible() is False
    assert dialog.finish_button.text() == "Finish Review"

    dialog.finish_button.click()
    QApplication.processEvents()
    assert session.is_finished()
    assert dialog.result() == dialog.DialogCode.Accepted


def test_final_finish_review_after_skip(qapp) -> None:
    only = _candidate("9785555555555", confidence_score=0.85)
    book = _book("Solo")
    session = ReviewSession.from_pairs([(book, _item(book, (only,)))])
    dialog = ReviewWizardDialog(session)
    dialog.show()
    QApplication.processEvents()

    assert dialog.finish_button.isVisible() is False
    dialog.skip_button.click()
    QApplication.processEvents()

    assert dialog.finish_button.isVisible() is True
    assert "1 skip" in dialog.finish_button.text()
    assert dialog.skip_button.isVisible() is False
    dialog.close()


def test_keyboard_selection_follows_auto_advance(qapp) -> None:
    session, c1a, _, _ = _three_book_session()
    dialog = ReviewWizardDialog(session, auto_advance_ms=0)
    dialog.show()
    QApplication.processEvents()

    card = dialog._cards[0]
    card.setFocus()
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_Space,
        Qt.KeyboardModifier.NoModifier,
    )
    card.keyPressEvent(event)
    QApplication.processEvents()

    assert session.decision_at(0).candidate == c1a
    assert session.current_index() == 1
    dialog.close()


def test_cancel_during_pending_transition_stops_timer(qapp) -> None:
    session, c1a, _, _ = _three_book_session()
    dialog = ReviewWizardDialog(session, auto_advance_ms=250)
    dialog.show()
    QApplication.processEvents()

    dialog._cards[0].clicked.emit(c1a)
    QApplication.processEvents()
    assert dialog._advance_timer.isActive() is True
    assert session.current_index() == 0

    dialog.cancel_button.click()
    QApplication.processEvents()

    assert dialog._advance_timer.isActive() is False
    assert session.current_index() == 0
    assert session.is_finished() is False
    assert dialog.result() == dialog.DialogCode.Rejected


def test_previous_cancels_pending_auto_advance(qapp) -> None:
    session, c1a, _, _ = _three_book_session()
    dialog = ReviewWizardDialog(session, auto_advance_ms=250)
    dialog.show()
    QApplication.processEvents()

    dialog.skip_button.click()
    QApplication.processEvents()
    assert session.current_index() == 1

    dialog._cards[0].clicked.emit(dialog._cards[0].candidate)
    QApplication.processEvents()
    assert dialog._advance_timer.isActive() is True

    dialog.previous_button.click()
    QApplication.processEvents()

    assert dialog._advance_timer.isActive() is False
    assert session.current_index() == 0
    assert session.decision_at(0).skipped is True
    dialog.close()


def test_preselect_very_high_does_not_auto_advance(qapp) -> None:
    only = _candidate("9784444444444", confidence_score=0.95)
    book1 = _book("Solo")
    book2 = _book("Next")
    c2 = _candidate("9785555555555", confidence_score=0.85)
    session = ReviewSession.from_pairs(
        [
            (book1, _item(book1, (only,))),
            (book2, _item(book2, (c2,))),
        ]
    )
    dialog = ReviewWizardDialog(session, auto_advance_ms=0)
    dialog.show()
    QApplication.processEvents()

    assert session.has_decision_for_current()
    assert session.current_index() == 0
    assert dialog._advance_timer.isActive() is False
    dialog.close()
