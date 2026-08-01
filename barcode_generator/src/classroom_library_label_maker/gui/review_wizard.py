"""Interactive ISBN review wizard — thin Qt presentation over ReviewSession.

All navigation and decision state lives on
:class:`~classroom_library_label_maker.services.book_review_service.ReviewSession`.
This dialog only renders the current item and forwards teacher actions.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
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


def _candidate_isbn_text(candidate: ReviewCandidate) -> str:
    isbn = (candidate.isbn13 or candidate.isbn10 or "").strip()
    return isbn or "No ISBN"


def _publication_year(candidate: ReviewCandidate) -> str:
    raw = (candidate.published_date or "").strip()
    if len(raw) >= 4 and raw[:4].isdigit():
        return raw[:4]
    return raw or "—"


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
        """Update visual selection styling."""
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        if selected:
            self.setStyleSheet(
                "QFrame#reviewCandidateCard {"
                "border: 2px solid #2a6f97; border-radius: 6px;"
                "background: #eef6fb;}"
                "QLabel#reviewConfidenceBadge {font-weight: 600;}"
                "QLabel#reviewRecommendedBadge {"
                "color: #1b4332; font-weight: 600;}"
            )
        else:
            self.setStyleSheet(
                "QFrame#reviewCandidateCard {"
                "border: 1px solid #c5c5c5; border-radius: 6px;"
                "background: #ffffff;}"
                "QLabel#reviewConfidenceBadge {font-weight: 600;}"
                "QLabel#reviewRecommendedBadge {"
                "color: #1b4332; font-weight: 600;}"
            )

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
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if session.item_count() < 1:
            raise ValueError("review session must contain at least one item")
        self._session = session
        self._cards: list[CandidateCard] = []
        self._refreshing = False

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
        root.addWidget(self.reason_label)

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
            "Remembered for a future release that writes the inventory. "
            "No workbook is written in this version."
        )
        root.addWidget(self.save_inventory_checkbox)

        nav = QHBoxLayout()
        self.previous_button = QPushButton("Previous")
        self.previous_button.setObjectName("reviewPreviousButton")
        self.previous_button.clicked.connect(self._on_previous)
        nav.addWidget(self.previous_button)

        self.next_button = QPushButton("Next")
        self.next_button.setObjectName("reviewNextButton")
        self.next_button.clicked.connect(self._on_next)
        nav.addWidget(self.next_button)

        nav.addStretch(1)

        self.skip_button = QPushButton("Skip This Book")
        self.skip_button.setObjectName("reviewSkipButton")
        self.skip_button.clicked.connect(self._on_skip)
        nav.addWidget(self.skip_button)

        self.finish_button = QPushButton("Finish")
        self.finish_button.setObjectName("reviewFinishButton")
        self.finish_button.setDefault(True)
        self.finish_button.clicked.connect(self._on_finish)
        nav.addWidget(self.finish_button)
        root.addLayout(nav)

        # Keep a standard reject path (Esc / window close) without Finish.
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.setObjectName("reviewCancelButtonBox")
        buttons.rejected.connect(self.reject)
        buttons.hide()
        root.addWidget(buttons)

        self._refresh()

    def session(self) -> ReviewSession:
        """Return the domain session driving this wizard."""
        return self._session

    def save_updated_inventory(self) -> bool:
        """Return whether the teacher wants inventory saved (preference only)."""
        return self.save_inventory_checkbox.isChecked()

    def _on_previous(self) -> None:
        if self._session.previous():
            self._refresh()

    def _on_next(self) -> None:
        if self._session.next():
            self._refresh()

    def _on_skip(self) -> None:
        self._session.skip_current()
        self._refresh()

    def _on_finish(self) -> None:
        self._session.finish()
        self.accept()

    def _on_candidate_clicked(self, candidate: object) -> None:
        if self._refreshing:
            return
        assert isinstance(candidate, ReviewCandidate)
        self._session.select_candidate(candidate)
        self._refresh_selection_styles()
        self._update_nav_enabled()

    def _refresh(self) -> None:
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

            if item is None or book is None:
                self.title_label.setText("")
                self.author_label.setText("")
                self.reason_label.setText("")
                self._rebuild_cards(())
                return

            self.title_label.setText(book.title)
            self.author_label.setText(f"by {book.author}")
            self.reason_label.setText(item.message)
            self._rebuild_cards(item.candidates)
            self._maybe_preselect_single_very_high(item.candidates)
            self._refresh_selection_styles()
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

    def _update_nav_enabled(self) -> None:
        index = self._session.current_index()
        total = self._session.item_count()
        self.previous_button.setEnabled(index > 0)
        self.next_button.setEnabled(index < total - 1)
        self.skip_button.setEnabled(total > 0)
        self.finish_button.setEnabled(True)
