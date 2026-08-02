"""Interactive ISBN review wizard — thin Qt presentation over ReviewSession.

All navigation and decision state lives on
:class:`~classroom_library_label_maker.services.book_review_service.ReviewSession`.
This dialog only renders the current item and forwards teacher actions.

Version 1.4 Phase 2 streamlines the click path; Phase 4 polishes presentation
(hierarchy, cards, badges, spacing) without changing workflow or domain logic.
Version 1.4.1 Phase 2 adds inline manual ISBN entry as an ordinary
``ReviewDecision`` (not a separate review state). Version 1.4.3 restores the
full interaction state for manual ISBN (Next / Finish, Edit ISBN, layout).
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPalette
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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

_MANUAL_ISBN_INVALID_MESSAGE = (
    "Invalid ISBN.\nPlease enter a valid ISBN-10 or ISBN-13."
)


def _candidate_isbn_text(candidate: ReviewCandidate) -> str:
    isbn = (candidate.isbn13 or candidate.isbn10 or "").strip()
    return isbn or "No ISBN"


def _publication_year(candidate: ReviewCandidate) -> str:
    raw = (candidate.published_date or "").strip()
    if len(raw) >= 4 and raw[:4].isdigit():
        return raw[:4]
    return raw or "—"


def _apply_manual_isbn_field_palette(edit: QLineEdit) -> None:
    """Force readable light-field colors under macOS dark mode."""
    palette = edit.palette()
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#111111"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#666666"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#1d6fa5"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    edit.setPalette(palette)


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
            "You can enter an ISBN manually, choose not to generate a label, "
            "or choose a catalog match if one is listed."
        )
    if item.status is BookEnrichmentStatus.ERROR:
        return (
            "We had trouble looking up this book.\n"
            "You can enter an ISBN manually, choose not to generate a label, "
            "or choose a catalog match if one is listed."
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

# Explicit light-surface colors so macOS dark mode does not paint system
# light text onto the card (white-on-white buttons / ghosted field text).
_MANUAL_ISBN_SECTION_STYLE = """
QFrame#reviewManualIsbnSection {
    background: #fafafa;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
}
QFrame#reviewManualIsbnSection QPushButton {
    background-color: #ffffff;
    color: #1a1a1a;
    border: 1px solid #bdbdbd;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 13px;
    font-weight: 500;
}
QFrame#reviewManualIsbnSection QPushButton:hover {
    background-color: #f3f7fb;
    border-color: #1d6fa5;
    color: #1a1a1a;
}
QFrame#reviewManualIsbnSection QPushButton:pressed {
    background-color: #e3f2fb;
    color: #1a1a1a;
}
QFrame#reviewManualIsbnSection QPushButton:focus {
    border: 2px solid #1d6fa5;
    color: #1a1a1a;
    outline: none;
}
QFrame#reviewManualIsbnSection QLineEdit {
    background-color: #ffffff;
    color: #111111;
    border: 1px solid #bdbdbd;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 13px;
    selection-background-color: #1d6fa5;
    selection-color: #ffffff;
}
QFrame#reviewManualIsbnSection QLineEdit:focus {
    background-color: #ffffff;
    color: #111111;
    border: 2px solid #1d6fa5;
}
QFrame#reviewManualIsbnSection QLabel {
    background: transparent;
    color: #333333;
}
"""


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
        self._manual_expanded: dict[int, bool] = {}
        self._manual_draft: dict[int, str] = {}
        self._manual_editing: dict[int, bool] = {}

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

        self._manual_section = self._build_manual_entry_section()
        candidates_layout.addWidget(self._manual_section)
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

        self.skip_button = QPushButton("Don't Generate Label")
        self.skip_button.setObjectName("reviewSkipButton")
        self.skip_button.setMinimumHeight(32)
        self.skip_button.setAccessibleName("Don't Generate Label")
        self.skip_button.setAccessibleDescription(
            "Do not generate a label for this book and continue to the next "
            "review item"
        )
        self.skip_button.clicked.connect(self._on_skip)
        nav.addWidget(self.skip_button)

        self.next_button = QPushButton("Next")
        self.next_button.setObjectName("reviewNextButton")
        self.next_button.setMinimumHeight(32)
        self.next_button.setAccessibleName("Next")
        self.next_button.setAccessibleDescription(
            "Continue to the next review book after a selection or skip"
        )
        self.next_button.clicked.connect(self._on_next)
        self.next_button.hide()
        nav.addWidget(self.next_button)

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

    def _build_manual_entry_section(self) -> QFrame:
        """Build the secondary manual ISBN path as a compact desktop form.

        Three states: collapsed (Enter ISBN Manually), editing (form), accepted
        (confirmation + Edit ISBN). Catalog matches stay the primary path.
        """
        section = QFrame()
        section.setObjectName("reviewManualIsbnSection")
        section.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        section.setStyleSheet(_MANUAL_ISBN_SECTION_STYLE)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        self.manual_prompt_label = QLabel("Can't find the correct edition?")
        self.manual_prompt_label.setObjectName("reviewManualIsbnPrompt")
        self.manual_prompt_label.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #555555;"
            "background: transparent;"
        )
        layout.addWidget(self.manual_prompt_label)

        self.manual_toggle_button = QPushButton("Enter ISBN Manually")
        self.manual_toggle_button.setObjectName("reviewManualIsbnToggle")
        self.manual_toggle_button.setMinimumHeight(32)
        self.manual_toggle_button.setMaximumWidth(200)
        self.manual_toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.manual_toggle_button.setAutoDefault(False)
        self.manual_toggle_button.setDefault(False)
        self.manual_toggle_button.setFlat(False)
        self.manual_toggle_button.setAccessibleName("Enter ISBN Manually")
        self.manual_toggle_button.setAccessibleDescription(
            "Expand the manual ISBN entry panel"
        )
        self.manual_toggle_button.clicked.connect(self._on_manual_toggle)
        layout.addWidget(
            self.manual_toggle_button,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )

        # Fixed width for a 13-digit ISBN field (not full-card stretch).
        isbn_field_width = 220

        self.manual_editor_panel = QWidget()
        self.manual_editor_panel.setObjectName("reviewManualIsbnEditor")
        self.manual_editor_panel.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground, True
        )
        editor_layout = QVBoxLayout(self.manual_editor_panel)
        editor_layout.setContentsMargins(0, 2, 0, 0)
        editor_layout.setSpacing(6)

        self.manual_isbn_field_label = QLabel("ISBN")
        self.manual_isbn_field_label.setObjectName("reviewManualIsbnFieldLabel")
        self.manual_isbn_field_label.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: #1a1a1a;"
            "background: transparent;"
        )
        editor_layout.addWidget(self.manual_isbn_field_label)

        self.manual_isbn_edit = QLineEdit()
        self.manual_isbn_edit.setObjectName("reviewManualIsbnEdit")
        # Help copy lives in the label below — avoid a second in-field string
        # that dark-mode / system styles can ghost-draw over the field.
        self.manual_isbn_edit.setPlaceholderText("")
        self.manual_isbn_edit.setClearButtonEnabled(True)
        self.manual_isbn_edit.setMinimumHeight(32)
        self.manual_isbn_edit.setFixedWidth(isbn_field_width)
        self.manual_isbn_edit.setAccessibleName("ISBN")
        self.manual_isbn_edit.setAccessibleDescription(
            "Paste or type an ISBN-10 or ISBN-13"
        )
        _apply_manual_isbn_field_palette(self.manual_isbn_edit)
        self.manual_isbn_edit.returnPressed.connect(self._on_apply_manual_isbn)
        self.manual_isbn_edit.textChanged.connect(self._on_manual_isbn_text_changed)
        editor_layout.addWidget(self.manual_isbn_edit)

        self.manual_help_label = QLabel("Paste or type an ISBN-10 or ISBN-13.")
        self.manual_help_label.setObjectName("reviewManualIsbnHelp")
        self.manual_help_label.setStyleSheet(
            "font-size: 12px; color: #555555; background: transparent;"
        )
        self.manual_help_label.setWordWrap(True)
        self.manual_help_label.setFixedWidth(isbn_field_width)
        editor_layout.addWidget(self.manual_help_label)

        self.manual_error_label = QLabel()
        self.manual_error_label.setObjectName("reviewManualIsbnError")
        self.manual_error_label.setWordWrap(True)
        self.manual_error_label.setFixedWidth(isbn_field_width)
        self.manual_error_label.setStyleSheet(
            "font-size: 12px; color: #b42318; font-weight: 600;"
            "background: transparent;"
        )
        self.manual_error_label.setAccessibleName("ISBN validation message")
        self.manual_error_label.hide()
        editor_layout.addWidget(self.manual_error_label)

        apply_host = QWidget()
        apply_host.setFixedWidth(isbn_field_width)
        apply_host_layout = QHBoxLayout(apply_host)
        apply_host_layout.setContentsMargins(0, 2, 0, 0)
        apply_host_layout.setSpacing(0)
        apply_host_layout.addStretch(1)
        self.manual_apply_button = QPushButton("Apply ISBN")
        self.manual_apply_button.setObjectName("reviewManualIsbnApply")
        self.manual_apply_button.setMinimumHeight(32)
        self.manual_apply_button.setFixedWidth(110)
        self.manual_apply_button.setAutoDefault(False)
        self.manual_apply_button.setDefault(False)
        self.manual_apply_button.setAccessibleName("Apply ISBN")
        self.manual_apply_button.setAccessibleDescription(
            "Validate and accept the entered ISBN"
        )
        self.manual_apply_button.clicked.connect(self._on_apply_manual_isbn)
        apply_host_layout.addWidget(self.manual_apply_button)
        editor_layout.addWidget(apply_host)

        self.manual_editor_panel.hide()
        layout.addWidget(self.manual_editor_panel)

        self.manual_accepted_panel = QWidget()
        self.manual_accepted_panel.setObjectName("reviewManualIsbnAccepted")
        accepted_layout = QVBoxLayout(self.manual_accepted_panel)
        accepted_layout.setContentsMargins(0, 2, 0, 0)
        accepted_layout.setSpacing(4)

        self.manual_accepted_title = QLabel("✓ Manual ISBN Accepted")
        self.manual_accepted_title.setObjectName("reviewManualIsbnAcceptedTitle")
        self.manual_accepted_title.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #0f5132;"
            "background: transparent;"
        )
        self.manual_accepted_title.setAccessibleName("Manual ISBN Accepted")
        accepted_layout.addWidget(self.manual_accepted_title)

        self.manual_accepted_isbn = QLabel()
        self.manual_accepted_isbn.setObjectName("reviewManualIsbnAcceptedValue")
        self.manual_accepted_isbn.setStyleSheet(
            "font-size: 14px; font-weight: 600; color: #111111;"
            "background: transparent;"
        )
        self.manual_accepted_isbn.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.manual_accepted_isbn.setAccessibleName("Accepted manual ISBN")
        accepted_layout.addWidget(self.manual_accepted_isbn)

        self.manual_edit_button = QPushButton("Edit ISBN")
        self.manual_edit_button.setObjectName("reviewManualIsbnEditButton")
        self.manual_edit_button.setMinimumHeight(32)
        self.manual_edit_button.setMaximumWidth(120)
        self.manual_edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.manual_edit_button.setAutoDefault(False)
        self.manual_edit_button.setDefault(False)
        self.manual_edit_button.setAccessibleName("Edit ISBN")
        self.manual_edit_button.setAccessibleDescription(
            "Edit the accepted manual ISBN"
        )
        self.manual_edit_button.clicked.connect(self._on_edit_manual_isbn)
        accepted_layout.addWidget(
            self.manual_edit_button,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )

        self.manual_accepted_panel.hide()
        layout.addWidget(self.manual_accepted_panel)

        return section

    def _on_manual_toggle(self) -> None:
        if self._refreshing:
            return
        index = self._session.current_index()
        if self._manual_editing.get(index, False) and (
            self._session.current_decision_is_manual()
        ):
            self._on_cancel_manual_edit()
            return
        self._persist_manual_draft()
        expanded = not self._manual_expanded.get(index, False)
        self._manual_expanded[index] = expanded
        if not expanded:
            self._manual_editing[index] = False
        self._sync_manual_entry_ui()
        if expanded:
            self.manual_isbn_edit.setFocus(Qt.FocusReason.TabFocusReason)

    def _on_edit_manual_isbn(self) -> None:
        """Open the editor with the accepted ISBN pre-filled (presentation only)."""
        if self._refreshing:
            return
        if not self._session.current_decision_is_manual():
            return
        decision = self._session.decision_for_current()
        assert decision is not None and decision.candidate is not None
        index = self._session.current_index()
        isbn = _candidate_isbn_text(decision.candidate)
        self._manual_editing[index] = True
        self._manual_expanded[index] = True
        self._manual_draft[index] = isbn
        self._sync_manual_entry_ui()
        self.manual_isbn_edit.setFocus(Qt.FocusReason.TabFocusReason)
        self.manual_isbn_edit.selectAll()

    def _on_cancel_manual_edit(self) -> None:
        """Leave the editor and restore the accepted manual ISBN view."""
        if self._refreshing:
            return
        index = self._session.current_index()
        self._manual_editing[index] = False
        self._manual_expanded[index] = False
        self._manual_draft.pop(index, None)
        self.manual_error_label.clear()
        self.manual_error_label.hide()
        self._sync_manual_entry_ui()

    def _on_manual_isbn_text_changed(self, _text: str) -> None:
        if self._refreshing:
            return
        if self.manual_error_label.isVisible():
            self.manual_error_label.clear()
            self.manual_error_label.hide()

    def _on_apply_manual_isbn(self) -> None:
        if self._refreshing:
            return
        raw = self.manual_isbn_edit.text()
        try:
            self._session.select_manual_isbn(raw)
        except ValueError:
            self.manual_error_label.setText(_MANUAL_ISBN_INVALID_MESSAGE)
            self.manual_error_label.show()
            self.manual_isbn_edit.setFocus(Qt.FocusReason.OtherFocusReason)
            return

        index = self._session.current_index()
        self._manual_expanded[index] = False
        self._manual_editing[index] = False
        self._manual_draft.pop(index, None)
        self.manual_error_label.clear()
        self.manual_error_label.hide()
        self._update_remaining_label()
        self._refresh_selection_styles(animate=False)
        self._update_decision_status()
        self._sync_manual_entry_ui()
        self._update_nav_enabled()
        self._schedule_auto_advance()

    def _persist_manual_draft(self) -> None:
        index = self._session.current_index()
        if self.manual_editor_panel.isVisible():
            self._manual_draft[index] = self.manual_isbn_edit.text()

    def _sync_manual_entry_ui(self) -> None:
        """Render one of three states: collapsed, editing, or accepted."""
        index = self._session.current_index()
        is_manual = self._session.current_decision_is_manual()
        editing = bool(self._manual_editing.get(index, False))

        if is_manual and not editing:
            decision = self._session.decision_for_current()
            assert decision is not None and decision.candidate is not None
            isbn = _candidate_isbn_text(decision.candidate)
            self.manual_toggle_button.hide()
            self.manual_editor_panel.hide()
            self.manual_accepted_panel.show()
            self.manual_accepted_isbn.setText(isbn)
            self.manual_error_label.clear()
            self.manual_error_label.hide()
            return

        self.manual_accepted_panel.hide()
        expanded = self._manual_expanded.get(index, False) or (
            is_manual and editing
        )
        if not expanded:
            self.manual_toggle_button.show()
            self.manual_toggle_button.setText("Enter ISBN Manually")
            self.manual_toggle_button.setAccessibleName("Enter ISBN Manually")
            self.manual_toggle_button.setAccessibleDescription(
                "Expand the manual ISBN entry panel"
            )
            self.manual_editor_panel.hide()
            return

        self.manual_toggle_button.show()
        self.manual_toggle_button.setText("Back to Matches")
        self.manual_toggle_button.setAccessibleName("Back to Matches")
        self.manual_toggle_button.setAccessibleDescription(
            "Close manual ISBN entry"
        )
        self.manual_editor_panel.show()
        draft = self._manual_draft.get(index, "")
        if self.manual_isbn_edit.text() != draft:
            self.manual_isbn_edit.setText(draft)
        self.manual_error_label.clear()
        self.manual_error_label.hide()

    def _on_previous(self) -> None:
        self._cancel_auto_advance()
        self._persist_manual_draft()
        if self._session.previous():
            self._refresh()

    def _on_next(self) -> None:
        """Advance when the current book already has a restored decision."""
        self._cancel_auto_advance()
        self._persist_manual_draft()
        if self._session.next():
            self._refresh()

    def _on_skip(self) -> None:
        if self._refreshing:
            return
        self._persist_manual_draft()
        index = self._session.current_index()
        self._manual_editing[index] = False
        self._session.skip_current()
        self._update_remaining_label()
        self._refresh_selection_styles(animate=False)
        self._update_decision_status()
        self._sync_manual_entry_ui()
        self._update_nav_enabled()
        self._schedule_auto_advance()

    def _on_finish(self) -> None:
        self._cancel_auto_advance()
        self._session.finish()
        self.accept()

    def _on_candidate_clicked(self, candidate: object) -> None:
        if self._refreshing:
            return
        assert isinstance(candidate, ReviewCandidate)
        self._persist_manual_draft()
        index = self._session.current_index()
        self._manual_expanded[index] = False
        self._manual_editing[index] = False
        self._session.select_candidate(candidate)
        self._update_remaining_label()
        self._refresh_selection_styles(animate=True)
        self._update_decision_status()
        self._sync_manual_entry_ui()
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
                self._sync_manual_entry_ui()
                self._update_nav_enabled()
                return

            self.title_label.setText(book.title)
            self.author_label.setText(f"by {book.author}")
            self.reason_label.setText(friendly_review_reason(item))
            self._rebuild_cards(item.candidates)
            self._maybe_preselect_single_very_high(item.candidates)
            self._refresh_selection_styles(animate=False)
            self._update_decision_status()
            self._sync_manual_entry_ui()
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
                "No catalog matches to choose from. Enter an ISBN manually "
                "or choose Don't Generate Label."
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
            self.decision_status_label.setText("✓ Label will not be generated")
            self.decision_status_label.setStyleSheet(
                "font-size: 13px; font-weight: 600; color: #0f5132;"
                "background: #e8f5ee; border: 1px solid #a3cfbb;"
                "border-radius: 6px; padding: 8px 10px; margin-top: 4px;"
            )
            self.decision_status_label.show()
            self._book_section.setStyleSheet(
                "QFrame#reviewBookSection {"
                "background: #f4fbf7; border: 1px solid #a3cfbb;"
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
        """Render nav from session state: unresolved → Skip; resolved → Next/Finish."""
        index = self._session.current_index()
        total = self._session.item_count()
        has_decision = self._session.has_decision_for_current()
        on_last = total > 0 and index >= total - 1
        show_finish = on_last and has_decision
        show_next = has_decision and not on_last

        self.previous_button.setEnabled(index > 0)
        self.skip_button.setVisible(not show_finish)
        self.skip_button.setEnabled(
            total > 0 and not self._session.is_finished() and not show_finish
        )
        self.next_button.setVisible(show_next)
        self.next_button.setEnabled(
            show_next and not self._session.is_finished()
        )
        self.finish_button.setVisible(show_finish)
        self.finish_button.setEnabled(show_finish)

        skipped = sum(1 for decision in self._session.decisions() if decision.skipped)
        if skipped > 0:
            label_word = "without a label" if skipped == 1 else "without labels"
            self.finish_button.setText(f"Finish Review ({skipped} {label_word})")
        else:
            self.finish_button.setText("Finish Review")
