"""Interactive ISBN review wizard — thin Qt presentation over ReviewSession.

All navigation and decision state lives on
:class:`~classroom_library_label_maker.services.book_review_service.ReviewSession`.
This dialog only renders the current item and forwards teacher actions.

Version 1.4 Phase 2 streamlines the click path; Phase 4 polishes presentation
(hierarchy, cards, badges, spacing) without changing workflow or domain logic.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from classroom_library_label_maker.models import (
    BookEnrichmentStatus,
    ReviewCandidate,
    ReviewItem,
)
from classroom_library_label_maker.services.book_review_service import ReviewSession

# Brief pause after a candidate click so teachers can still change their mind.
DEFAULT_AUTO_ADVANCE_MS = 250
# Subtle selected-state checkmark fade (presentation only).
_CHECKMARK_ANIM_MS = 150


def _candidate_isbn_text(candidate: ReviewCandidate) -> str:
    isbn = (candidate.isbn13 or candidate.isbn10 or "").strip()
    return isbn or "No ISBN"


def _publication_year(candidate: ReviewCandidate) -> str:
    raw = (candidate.published_date or "").strip()
    if len(raw) >= 4 and raw[:4].isdigit():
        return raw[:4]
    return raw or "—"


def friendly_review_reason(item: ReviewItem) -> str:
    """Return teacher-facing review guidance (presentation only)."""
    if item.status is BookEnrichmentStatus.AMBIGUOUS:
        return (
            "We found multiple matching editions.\n"
            "Please choose the one that matches your book."
        )
    if item.status is BookEnrichmentStatus.NOT_FOUND:
        return (
            "We couldn't find a clear ISBN match for this book.\n"
            "You can skip it, or choose a catalog match if one is listed."
        )
    if item.status is BookEnrichmentStatus.ERROR:
        return (
            "We had trouble looking up this book.\n"
            "You can skip it, or choose a catalog match if one is listed."
        )
    message = (item.message or "").strip()
    return message or (
        "Please review the catalog matches and choose the edition "
        "that matches your book."
    )


_CARD_LABEL_STYLE = (
    "QLabel#reviewConfidenceBadge {color: #1a1a1a; font-weight: 600; font-size: 12px;}"
    "QLabel#reviewRecommendedBadge {color: #0f5132; font-weight: 700; font-size: 12px;}"
    "QLabel#reviewCandidateCheck {color: #1d6fa5; font-weight: 700; font-size: 18px;}"
    "QLabel#reviewCandidateIsbn {color: #1a1a1a; font-size: 13px;}"
    "QLabel#reviewCandidateTitle {color: #111111; font-weight: 600; font-size: 14px;}"
    "QLabel#reviewCandidateAuthor {color: #333333; font-size: 13px;}"
    "QLabel#reviewCandidateMeta {color: #555555; font-size: 12px;}"
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
        self._recommended = recommended
        self.setObjectName("reviewCandidateCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(
            (
                f"Recommended Match — {candidate.confidence_label} Match — "
                f"{_candidate_isbn_text(candidate)}"
                if recommended
                else (
                    f"{candidate.confidence_label} Match — "
                    f"{_candidate_isbn_text(candidate)}"
                )
            )
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        badges = QVBoxLayout()
        badges.setContentsMargins(0, 0, 0, 0)
        badges.setSpacing(2)

        if recommended:
            recommended_label = QLabel("⭐ Recommended Match")
            recommended_label.setObjectName("reviewRecommendedBadge")
            recommended_label.setAccessibleName("Recommended Match")
            badges.addWidget(recommended_label)
            confidence = QLabel(f"{candidate.confidence_label} Match")
            confidence.setObjectName("reviewConfidenceBadge")
            badges.addWidget(confidence)
        else:
            badge = QLabel(f"{candidate.confidence_label} Match")
            badge.setObjectName("reviewConfidenceBadge")
            badges.addWidget(badge)

        header.addLayout(badges, 1)
        self.check_label = QLabel("✓")
        self.check_label.setObjectName("reviewCandidateCheck")
        self.check_label.setAccessibleName("Selected")
        self.check_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )
        self._check_opacity = QGraphicsOpacityEffect(self.check_label)
        self._check_opacity.setOpacity(0.0)
        self.check_label.setGraphicsEffect(self._check_opacity)
        self.check_label.hide()
        self._check_anim = QPropertyAnimation(self._check_opacity, b"opacity", self)
        self._check_anim.setDuration(_CHECKMARK_ANIM_MS)
        self._check_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        header.addWidget(self.check_label, 0)
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

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(0)
        self._shadow.setOffset(0, 0)
        self._shadow.setColor(QColor(29, 111, 165, 0))
        self.setGraphicsEffect(self._shadow)

        self.set_selected(False, animate=False)

    def is_recommended(self) -> bool:
        """True when this card shows the Recommended Match badge."""
        return self._recommended

    def set_selected(self, selected: bool, *, animate: bool = True) -> None:
        """Update visual selection styling.

        Cards always use a light surface with explicit dark label colors so
        text stays readable under macOS dark mode (system text would otherwise
        be light-on-light).
        """
        self.setProperty("selected", selected)
        self.setAccessibleDescription("Selected" if selected else "")
        self.style().unpolish(self)
        self.style().polish(self)

        if selected:
            frame = (
                "QFrame#reviewCandidateCard {"
                "border: 3px solid #1d6fa5; border-radius: 8px;"
                "background: #e3f2fb;}"
            )
            self._shadow.setBlurRadius(16)
            self._shadow.setOffset(0, 3)
            self._shadow.setColor(QColor(29, 111, 165, 70))
            self._show_checkmark(animate=animate)
        else:
            frame = (
                "QFrame#reviewCandidateCard {"
                "border: 1px solid #c4c4c4; border-radius: 8px;"
                "background: #f7f7f7;}"
            )
            self._shadow.setBlurRadius(0)
            self._shadow.setOffset(0, 0)
            self._shadow.setColor(QColor(29, 111, 165, 0))
            self._hide_checkmark(animate=animate)

        self.setStyleSheet(frame + _CARD_LABEL_STYLE)

    def _show_checkmark(self, *, animate: bool) -> None:
        self.check_label.show()
        self._check_anim.stop()
        if not animate:
            self._check_opacity.setOpacity(1.0)
            return
        self._check_anim.setStartValue(self._check_opacity.opacity())
        self._check_anim.setEndValue(1.0)
        self._check_anim.start()

    def _hide_checkmark(self, *, animate: bool) -> None:
        self._check_anim.stop()
        if not animate:
            self._check_opacity.setOpacity(0.0)
            self.check_label.hide()
            return

        def _finish() -> None:
            if self._check_opacity.opacity() <= 0.01:
                self.check_label.hide()

        self._check_anim.finished.connect(
            _finish,
            Qt.ConnectionType.SingleShotConnection,
        )
        self._check_anim.setStartValue(self._check_opacity.opacity())
        self._check_anim.setEndValue(0.0)
        self._check_anim.start()

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
        self.setMinimumSize(600, 560)
        self.resize(700, 660)
        self.setAccessibleName("Review ISBN Matches")

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(22)

        # --- Progress ---
        progress_section = QWidget()
        progress_section.setObjectName("reviewProgressSection")
        progress_layout = QVBoxLayout(progress_section)
        progress_layout.setContentsMargins(0, 0, 0, 8)
        progress_layout.setSpacing(8)

        self.section_title_label = QLabel("Review ISBN Matches")
        self.section_title_label.setObjectName("reviewSectionTitle")
        self.section_title_label.setStyleSheet(
            "font-size: 20px; font-weight: 700; color: #111111;"
        )
        self.section_title_label.setAccessibleName("Review ISBN Matches")
        progress_layout.addWidget(self.section_title_label)

        self.progress_label = QLabel()
        self.progress_label.setObjectName("reviewProgressLabel")
        self.progress_label.setStyleSheet(
            "font-size: 14px; font-weight: 600; color: #333333;"
        )
        self.progress_label.setAccessibleName("Review progress")
        progress_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("reviewProgressBar")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMinimumHeight(10)
        self.progress_bar.setMaximumHeight(10)
        self.progress_bar.setStyleSheet(
            "QProgressBar {border: none; border-radius: 5px; background: #e5e5e5;}"
            "QProgressBar::chunk {border-radius: 5px; background: #1d6fa5;}"
        )
        progress_layout.addWidget(self.progress_bar)

        self.remaining_label = QLabel()
        self.remaining_label.setObjectName("reviewRemainingLabel")
        self.remaining_label.setStyleSheet("font-size: 13px; color: #666666;")
        self.remaining_label.setAccessibleName("Books remaining")
        progress_layout.addWidget(self.remaining_label)
        root.addWidget(progress_section)

        # --- Book information ---
        book_section = QFrame()
        book_section.setObjectName("reviewBookSection")
        book_section.setStyleSheet(
            "QFrame#reviewBookSection {"
            "background: #fafafa; border: 1px solid #e8e8e8;"
            "border-radius: 8px;}"
        )
        self._book_section = book_section
        book_layout = QVBoxLayout(book_section)
        book_layout.setContentsMargins(18, 16, 18, 16)
        book_layout.setSpacing(8)

        self.title_label = QLabel()
        self.title_label.setObjectName("reviewBookTitle")
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet(
            "font-size: 17px; font-weight: 700; color: #111111;"
        )
        book_layout.addWidget(self.title_label)

        self.author_label = QLabel()
        self.author_label.setObjectName("reviewBookAuthor")
        self.author_label.setWordWrap(True)
        self.author_label.setStyleSheet("font-size: 14px; color: #444444;")
        book_layout.addWidget(self.author_label)

        self.reason_label = QLabel()
        self.reason_label.setObjectName("reviewReasonLabel")
        self.reason_label.setWordWrap(True)
        self.reason_label.setStyleSheet(
            "font-size: 13px; color: #b45309; margin-top: 4px;"
        )
        self.reason_label.setAccessibleName("Review guidance")
        book_layout.addWidget(self.reason_label)

        self.decision_status_label = QLabel()
        self.decision_status_label.setObjectName("reviewDecisionStatus")
        self.decision_status_label.setWordWrap(True)
        self.decision_status_label.setAccessibleName("Review decision status")
        book_layout.addWidget(self.decision_status_label)
        root.addWidget(book_section)

        # --- Candidate selection ---
        candidates_section = QWidget()
        candidates_section.setObjectName("reviewCandidatesSection")
        candidates_layout = QVBoxLayout(candidates_section)
        candidates_layout.setContentsMargins(0, 0, 0, 0)
        candidates_layout.setSpacing(10)

        self.candidates_caption = QLabel("Choose a catalog match")
        self.candidates_caption.setObjectName("reviewCandidatesCaption")
        self.candidates_caption.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #555555;"
        )
        candidates_layout.addWidget(self.candidates_caption)

        self._candidates_host = QWidget()
        self._candidates_layout = QVBoxLayout(self._candidates_host)
        self._candidates_layout.setContentsMargins(0, 0, 4, 0)
        self._candidates_layout.setSpacing(12)
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
        candidates_layout.addWidget(scroll, stretch=1)
        root.addWidget(candidates_section, stretch=1)

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
        nav.setSpacing(12)
        self.previous_button = QPushButton("Previous")
        self.previous_button.setObjectName("reviewPreviousButton")
        self.previous_button.setMinimumHeight(32)
        self.previous_button.setAccessibleName("Previous")
        self.previous_button.setAccessibleDescription(
            "Return to the previous review book"
        )
        self.previous_button.clicked.connect(self._on_previous)
        nav.addWidget(self.previous_button)

        self.skip_button = QPushButton("Skip")
        self.skip_button.setObjectName("reviewSkipButton")
        self.skip_button.setMinimumHeight(32)
        self.skip_button.setAccessibleName("Skip")
        self.skip_button.setAccessibleDescription(
            "Skip this book and continue to the next review item"
        )
        self.skip_button.clicked.connect(self._on_skip)
        nav.addWidget(self.skip_button)

        self.finish_button = QPushButton("Finish Review")
        self.finish_button.setObjectName("reviewFinishButton")
        self.finish_button.setMinimumHeight(32)
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
        self.cancel_button.setMinimumHeight(32)
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
        self._refresh_selection_styles(animate=True)
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
        self.remaining_label.setText(f"{remaining} Remaining")

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
            self.reason_label.setText(friendly_review_reason(item))
            self._rebuild_cards(item.candidates)
            self._maybe_preselect_single_very_high(item.candidates)
            self._refresh_selection_styles(animate=False)
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
            empty.setStyleSheet("color: #777777; font-size: 13px;")
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

    def _refresh_selection_styles(self, *, animate: bool = False) -> None:
        decision = self._session.decision_for_current()
        selected = (
            None if decision is None or decision.skipped else decision.candidate
        )
        for card in self._cards:
            card.set_selected(
                selected is not None and card.candidate == selected,
                animate=animate,
            )

    def _update_decision_status(self) -> None:
        decision = self._session.decision_for_current()
        if decision is None:
            self.decision_status_label.clear()
            self.decision_status_label.hide()
            self._book_section.setStyleSheet(
                "QFrame#reviewBookSection {"
                "background: #fafafa; border: 1px solid #e8e8e8;"
                "border-radius: 8px;}"
            )
            return
        if decision.skipped:
            self.decision_status_label.setText("This book will be skipped.")
            self.decision_status_label.setStyleSheet(
                "font-size: 13px; font-weight: 600; color: #6b5b00;"
                "background: #fff8db; border: 1px solid #e6d98a;"
                "border-radius: 6px; padding: 8px 10px; margin-top: 4px;"
            )
            self.decision_status_label.show()
            self._book_section.setStyleSheet(
                "QFrame#reviewBookSection {"
                "background: #fffdf5; border: 1px solid #e6d98a;"
                "border-radius: 8px;}"
            )
            return
        self.decision_status_label.setText("Selected")
        self.decision_status_label.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #1d6fa5; margin-top: 2px;"
        )
        self.decision_status_label.show()
        self._book_section.setStyleSheet(
            "QFrame#reviewBookSection {"
            "background: #fafafa; border: 1px solid #e8e8e8;"
            "border-radius: 8px;}"
        )

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
