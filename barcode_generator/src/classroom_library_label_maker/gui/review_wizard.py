"""Interactive ISBN review wizard — thin Qt presentation over ReviewSession.

All navigation and decision state lives on
:class:`~classroom_library_label_maker.services.book_review_service.ReviewSession`.
This dialog only renders the current item and forwards teacher actions.

Version 1.4 Phase 2 streamlines the click path: Skip advances immediately;
candidate selection highlights at once and auto-advances after a short delay.
Business logic on :class:`ReviewSession` / :class:`BookReviewService` is
unchanged.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from classroom_library_label_maker.models import ReviewCandidate
from classroom_library_label_maker.services.book_review_service import ReviewSession

# Brief pause after a candidate click so teachers can still change their mind.
DEFAULT_AUTO_ADVANCE_MS = 250


def _candidate_isbn_text(candidate: ReviewCandidate) -> str:
    isbn = (candidate.isbn13 or candidate.isbn10 or "").strip()
    return isbn or "No ISBN"


def _publication_year(candidate: ReviewCandidate) -> str:
    raw = (candidate.published_date or "").strip()
    if len(raw) >= 4 and raw[:4].isdigit():
        return raw[:4]
    return raw or "—"


_CARD_LABEL_STYLE = (
    "QLabel#reviewConfidenceBadge {color: #1a1a1a; font-weight: 600;}"
    "QLabel#reviewRecommendedBadge {color: #146c43; font-weight: 600;}"
    "QLabel#reviewCandidateCheck {color: #2a6f97; font-weight: 700; font-size: 16px;}"
    "QLabel#reviewCandidateIsbn {color: #1a1a1a;}"
    "QLabel#reviewCandidateTitle {color: #111111; font-weight: 600;}"
    "QLabel#reviewCandidateAuthor {color: #333333;}"
    "QLabel#reviewCandidateMeta {color: #555555;}"
)


class CandidateCard(QFrame):
    """Selectable card for one preserved catalog candidate."""

    clicked = Signal(object)

    def __init__(
        self,
        candidate: ReviewCandidate,
        *,
        recommended: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.candidate = candidate
        self.setObjectName("reviewCandidateCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(
            f"{candidate.confidence_label} Match — {_candidate_isbn_text(candidate)}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(4)

        header = QHBoxLayout()
        badge = QLabel(f"{candidate.confidence_label} Match")
        badge.setObjectName("reviewConfidenceBadge")
        header.addWidget(badge)
        header.addStretch(1)
        if recommended:
            recommended_label = QLabel("Recommended")
            recommended_label.setObjectName("reviewRecommendedBadge")
            recommended_label.setAccessibleName("Recommended")
            header.addWidget(recommended_label)
        self.check_label = QLabel("✓")
        self.check_label.setObjectName("reviewCandidateCheck")
        self.check_label.setAccessibleName("Selected")
        self.check_label.hide()
        header.addWidget(self.check_label)
        root.addLayout(header)

        isbn_label = QLabel(_candidate_isbn_text(candidate))
        isbn_label.setObjectName("reviewCandidateIsbn")
        root.addWidget(isbn_label)

        title_label = QLabel(candidate.title or "—")
        title_label.setObjectName("reviewCandidateTitle")
        title_label.setWordWrap(True)
        root.addWidget(title_label)

        author_label = QLabel(candidate.author or "—")
        author_label.setObjectName("reviewCandidateAuthor")
        author_label.setWordWrap(True)
        root.addWidget(author_label)

        meta = QLabel(
            f"{candidate.publisher or '—'} · {_publication_year(candidate)}"
        )
        meta.setObjectName("reviewCandidateMeta")
        meta.setWordWrap(True)
        root.addWidget(meta)

        self.set_selected(False)

    def set_selected(self, selected: bool) -> None:
        """Update visual selection styling.

        Cards always use a light surface with explicit dark label colors so
        text stays readable under macOS dark mode (system text would otherwise
        be light-on-light).
        """
        self.setProperty("selected", selected)
        self.check_label.setVisible(selected)
        self.setAccessibleDescription("Selected" if selected else "")
        self.style().unpolish(self)
        self.style().polish(self)
        if selected:
            frame = (
                "QFrame#reviewCandidateCard {"
                "border: 2px solid #2a6f97; border-radius: 6px;"
                "background: #e8f4fc;}"
            )
        else:
            frame = (
                "QFrame#reviewCandidateCard {"
                "border: 1px solid #b0b0b0; border-radius: 6px;"
                "background: #f5f5f5;}"
            )
        self.setStyleSheet(frame + _CARD_LABEL_STYLE)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.candidate)
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit(self.candidate)
            return
        super().keyPressEvent(event)


class ReviewWizardDialog(QDialog):
    """Modal review wizard driven entirely by a :class:`ReviewSession`."""

    def __init__(
        self,
        session: ReviewSession,
        *,
        save_updated_inventory: bool = True,
        auto_advance_ms: int = DEFAULT_AUTO_ADVANCE_MS,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if session.item_count() < 1:
            raise ValueError("review session must contain at least one item")
        self._session = session
        self._cards: list[CandidateCard] = []
        self._refreshing = False
        self._auto_advance_ms = max(0, int(auto_advance_ms))

        self.setWindowTitle("Review ISBN Matches")
        self.setObjectName("reviewWizardDialog")
        self.setModal(True)
        self.setMinimumSize(560, 520)
        self.resize(640, 600)
        self.setAccessibleName("Review ISBN Matches")

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        self.progress_label = QLabel()
        self.progress_label.setObjectName("reviewProgressLabel")
        self.progress_label.setAccessibleName("Review progress")
        root.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("reviewProgressBar")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMinimum(0)
        root.addWidget(self.progress_bar)

        self.remaining_label = QLabel()
        self.remaining_label.setObjectName("reviewRemainingLabel")
        self.remaining_label.setAccessibleName("Books remaining")
        root.addWidget(self.remaining_label)

        self.title_label = QLabel()
        self.title_label.setObjectName("reviewBookTitle")
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        root.addWidget(self.title_label)

        self.author_label = QLabel()
        self.author_label.setObjectName("reviewBookAuthor")
        self.author_label.setWordWrap(True)
        root.addWidget(self.author_label)

        self.reason_label = QLabel()
        self.reason_label.setObjectName("reviewReasonLabel")
        self.reason_label.setWordWrap(True)
        self.reason_label.setStyleSheet("color: #b45309;")
        root.addWidget(self.reason_label)

        self.decision_status_label = QLabel()
        self.decision_status_label.setObjectName("reviewDecisionStatus")
        self.decision_status_label.setWordWrap(True)
        self.decision_status_label.setAccessibleName("Review decision status")
        root.addWidget(self.decision_status_label)

        candidates_caption = QLabel("Catalog matches")
        candidates_caption.setObjectName("reviewCandidatesCaption")
        root.addWidget(candidates_caption)

        self._candidates_host = QWidget()
        self._candidates_layout = QVBoxLayout(self._candidates_host)
        self._candidates_layout.setContentsMargins(0, 0, 0, 0)
        self._candidates_layout.setSpacing(8)
        self._candidates_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setObjectName("reviewCandidatesScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self._candidates_host)
        scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        root.addWidget(scroll, stretch=1)

        self.save_inventory_checkbox = QCheckBox(
            "Save updated inventory workbook when review is complete"
        )
        self.save_inventory_checkbox.setObjectName("reviewSaveInventoryCheckbox")
        self.save_inventory_checkbox.setChecked(save_updated_inventory)
        self.save_inventory_checkbox.setToolTip(
            "Write a new inventory workbook with accepted and automatically "
            "found ISBNs. Your original inventory file is never overwritten."
        )
        root.addWidget(self.save_inventory_checkbox)

        nav = QHBoxLayout()
        self.previous_button = QPushButton("Previous")
        self.previous_button.setObjectName("reviewPreviousButton")
        self.previous_button.setAccessibleName("Previous")
        self.previous_button.setAccessibleDescription(
            "Return to the previous review book"
        )
        self.previous_button.clicked.connect(self._on_previous)
        nav.addWidget(self.previous_button)

        self.skip_button = QPushButton("Skip")
        self.skip_button.setObjectName("reviewSkipButton")
        self.skip_button.setAccessibleName("Skip")
        self.skip_button.setAccessibleDescription(
            "Skip this book and continue to the next review item"
        )
        self.skip_button.clicked.connect(self._on_skip)
        nav.addWidget(self.skip_button)

        self.finish_button = QPushButton("Finish Review")
        self.finish_button.setObjectName("reviewFinishButton")
        self.finish_button.setAccessibleName("Finish Review")
        self.finish_button.setAccessibleDescription(
            "Finish review after the last book has a selection or skip"
        )
        self.finish_button.setDefault(True)
        self.finish_button.clicked.connect(self._on_finish)
        self.finish_button.hide()
        nav.addWidget(self.finish_button)

        nav.addStretch(1)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("reviewCancelButton")
        self.cancel_button.setAccessibleName("Cancel")
        self.cancel_button.setAccessibleDescription(
            "Cancel review without applying decisions"
        )
        self.cancel_button.clicked.connect(self.reject)
        nav.addWidget(self.cancel_button)
        root.addLayout(nav)

        self._advance_timer = QTimer(self)
        self._advance_timer.setSingleShot(True)
        self._advance_timer.timeout.connect(self._on_auto_advance_timeout)

        self._refresh()

    def session(self) -> ReviewSession:
        """Return the domain session driving this wizard."""
        return self._session

    def save_updated_inventory(self) -> bool:
        """Return whether the teacher wants inventory saved (preference only)."""
        return self.save_inventory_checkbox.isChecked()

    def reject(self) -> None:
        """Cancel any pending auto-advance, then close without applying."""
        self._cancel_auto_advance()
        super().reject()

    def _on_previous(self) -> None:
        self._cancel_auto_advance()
        if self._session.previous():
            self._refresh()

    def _on_skip(self) -> None:
        self._cancel_auto_advance()
        self._session.skip_current()
        if self._session.next():
            self._refresh()
            return
        self._refresh()

    def _on_finish(self) -> None:
        self._cancel_auto_advance()
        self._session.finish()
        self.accept()

    def _on_candidate_clicked(self, candidate: object) -> None:
        if self._refreshing:
            return
        assert isinstance(candidate, ReviewCandidate)
        self._session.select_candidate(candidate)
        self._update_remaining_label()
        self._refresh_selection_styles()
        self._update_decision_status()
        self._update_nav_enabled()
        self._schedule_auto_advance()

    def _schedule_auto_advance(self) -> None:
        """Start or restart the post-selection advance timer."""
        self._advance_timer.stop()
        if self._is_on_final_item():
            return
        self._advance_timer.start(self._auto_advance_ms)

    def _cancel_auto_advance(self) -> None:
        self._advance_timer.stop()

    def _on_auto_advance_timeout(self) -> None:
        if self._session.next():
            self._refresh()

    def _is_on_final_item(self) -> bool:
        total = self._session.item_count()
        if total < 1:
            return False
        return self._session.current_index() >= total - 1

    def _update_remaining_label(self) -> None:
        remaining = self._session.remaining_count()
        remaining_word = "book" if remaining == 1 else "books"
        self.remaining_label.setText(f"{remaining} {remaining_word} remaining")

    def _refresh(self) -> None:
        self._cancel_auto_advance()
        self._refreshing = True
        try:
            item = self._session.current_item()
            book = self._session.current_book()
            total = self._session.item_count()
            index = self._session.current_index()
            human = index + 1 if total else 0

            self.progress_label.setText(f"Book {human} of {total}")
            self.progress_bar.setMaximum(max(total, 1))
            self.progress_bar.setValue(human)
            self._update_remaining_label()

            if item is None or book is None:
                self.title_label.setText("")
                self.author_label.setText("")
                self.reason_label.setText("")
                self.decision_status_label.clear()
                self._rebuild_cards(())
                self._update_nav_enabled()
                return

            self.title_label.setText(book.title)
            self.author_label.setText(f"by {book.author}")
            self.reason_label.setText(item.message)
            self._rebuild_cards(item.candidates)
            self._maybe_preselect_single_very_high(item.candidates)
            self._refresh_selection_styles()
            self._update_decision_status()
            self._update_nav_enabled()
        finally:
            self._refreshing = False

    def _rebuild_cards(self, candidates: tuple[ReviewCandidate, ...]) -> None:
        while self._candidates_layout.count():
            layout_item = self._candidates_layout.takeAt(0)
            widget = layout_item.widget()
            if widget is not None:
                widget.deleteLater()
        self._cards.clear()

        if not candidates:
            empty = QLabel(
                "No catalog matches to choose from. You can skip this book."
            )
            empty.setObjectName("reviewCandidatesEmpty")
            empty.setWordWrap(True)
            empty.setStyleSheet("color: #cccccc;")
            self._candidates_layout.addWidget(empty)
            self._candidates_layout.addStretch(1)
            return

        best_score = max(c.confidence_score for c in candidates)
        recommended_assigned = False
        for candidate in candidates:
            recommended = (
                not recommended_assigned and candidate.confidence_score == best_score
            )
            if recommended:
                recommended_assigned = True
            card = CandidateCard(candidate, recommended=recommended)
            card.clicked.connect(self._on_candidate_clicked)
            self._cards.append(card)
            self._candidates_layout.addWidget(card)
        self._candidates_layout.addStretch(1)

    def _maybe_preselect_single_very_high(
        self,
        candidates: tuple[ReviewCandidate, ...],
    ) -> None:
        """Pre-select a lone Very High match without auto-advancing."""
        if self._session.has_decision_for_current():
            return
        if len(candidates) != 1:
            return
        candidate = candidates[0]
        if candidate.confidence_label != "Very High":
            return
        self._session.select_candidate(candidate)

    def _refresh_selection_styles(self) -> None:
        decision = self._session.decision_for_current()
        selected = (
            None if decision is None or decision.skipped else decision.candidate
        )
        for card in self._cards:
            card.set_selected(selected is not None and card.candidate == selected)

    def _update_decision_status(self) -> None:
        decision = self._session.decision_for_current()
        if decision is None:
            self.decision_status_label.clear()
            return
        if decision.skipped:
            self.decision_status_label.setText(
                "Skipped — original ISBN left unchanged"
            )
            self.decision_status_label.setStyleSheet("color: #666666;")
            return
        self.decision_status_label.setText("Selected")
        self.decision_status_label.setStyleSheet("color: #2a6f97; font-weight: 600;")

    def _update_nav_enabled(self) -> None:
        index = self._session.current_index()
        total = self._session.item_count()
        has_decision = self._session.has_decision_for_current()
        on_last = total > 0 and index >= total - 1
        show_finish = on_last and has_decision

        self.previous_button.setEnabled(index > 0)
        self.skip_button.setVisible(not show_finish)
        self.skip_button.setEnabled(
            total > 0 and not self._session.is_finished() and not show_finish
        )
        self.finish_button.setVisible(show_finish)
        self.finish_button.setEnabled(show_finish)

        skipped = sum(1 for decision in self._session.decisions() if decision.skipped)
        if skipped > 0:
            skip_word = "skip" if skipped == 1 else "skips"
            self.finish_button.setText(f"Finish Review ({skipped} {skip_word})")
        else:
            self.finish_button.setText("Finish Review")
