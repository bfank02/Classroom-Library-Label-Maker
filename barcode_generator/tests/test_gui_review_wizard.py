"""GUI tests for the interactive ISBN review wizard."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from classroom_library_label_maker.gui.app import create_application
from classroom_library_label_maker.gui.controller import (
    GuiController,
    ReviewWizardOutcome,
)
from classroom_library_label_maker.gui.main_window import MainWindow
from classroom_library_label_maker.gui.review_wizard import ReviewWizardDialog
from classroom_library_label_maker.gui_preferences import (
    GuiPreferences,
    load_gui_preferences,
    save_gui_preferences,
)
from classroom_library_label_maker.models import (
    Book,
    BookEnrichmentStatus,
    EnrichmentSummary,
    ReviewCandidate,
    ReviewItem,
    WorkbookGenerationResult,
)
from classroom_library_label_maker.services.book_review_service import (
    BookReviewService,
    ReviewSession,
)
from gui_test_helpers import wait_until_generation_finished


@pytest.fixture(scope="module")
def qapp():
    app = create_application(["classroom-library-label-maker-gui-review-test"])
    yield app


def _book(title: str, *, isbn: str = "MISSING") -> Book:
    return Book(isbn=isbn, title=title, author="Author", copies=1)


def _candidate(
    isbn13: str,
    *,
    title: str = "Catalog Title",
    author: str = "Catalog Author",
    confidence_score: float = 0.91,
    publisher: str = "Pub",
    published_date: str = "2005-01-01",
) -> ReviewCandidate:
    return ReviewCandidate(
        isbn13=isbn13,
        title=title,
        author=author,
        publisher=publisher,
        published_date=published_date,
        confidence_score=confidence_score,
    )


def _item(
    book: Book,
    candidates: tuple[ReviewCandidate, ...],
    *,
    message: str = "Multiple catalog matches",
) -> ReviewItem:
    return ReviewItem(
        title=book.title,
        author=book.author,
        status=BookEnrichmentStatus.AMBIGUOUS,
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


def test_wizard_progress_and_navigation(qapp) -> None:
    session, c1a, _ = _two_book_session()
    dialog = ReviewWizardDialog(session, auto_advance_ms=0)
    dialog.show()
    QApplication.processEvents()

    assert dialog.progress_label.text() == "Book 1 of 2"
    assert dialog.progress_bar.value() == 1
    assert dialog.progress_bar.maximum() == 2
    assert dialog.remaining_label.text() == "2 Remaining"
    assert dialog.title_label.text() == "Book One"
    assert "Author" in dialog.author_label.text()
    assert "multiple matching editions" in dialog.reason_label.text().lower()
    assert "b45309" in dialog.reason_label.styleSheet()
    assert dialog.previous_button.isEnabled() is False
    assert dialog.skip_button.isVisible() is True
    assert dialog.finish_button.isVisible() is False
    assert dialog.cancel_button.isVisible() is True
    assert not hasattr(dialog, "next_button")

    dialog._cards[0].clicked.emit(c1a)
    QApplication.processEvents()
    assert dialog.remaining_label.text() == "1 Remaining"
    assert dialog.progress_label.text() == "Book 2 of 2"
    assert dialog.progress_bar.value() == 2
    assert dialog.title_label.text() == "Book Two"
    assert dialog.previous_button.isEnabled() is True

    dialog.skip_button.click()
    QApplication.processEvents()
    assert dialog.finish_button.isVisible() is True
    assert "1 skip" in dialog.finish_button.text()
    assert dialog.skip_button.isVisible() is False

    dialog.previous_button.click()
    QApplication.processEvents()
    assert dialog.progress_label.text() == "Book 1 of 2"
    assert dialog._cards[0].property("selected") is True
    dialog.close()


def test_wizard_recommended_badge_on_highest_confidence(qapp) -> None:
    session, c1a, _ = _two_book_session()
    dialog = ReviewWizardDialog(session)
    dialog.show()
    QApplication.processEvents()

    badges = dialog.findChildren(QLabel, "reviewRecommendedBadge")
    assert len(badges) == 1
    assert badges[0].text() == "⭐ Recommended Match"
    assert dialog._cards[0].candidate == c1a
    assert dialog._cards[0].findChild(QLabel, "reviewRecommendedBadge") is not None
    assert dialog._cards[1].findChild(QLabel, "reviewRecommendedBadge") is None
    dialog.close()


def test_wizard_candidate_selection_updates_session(qapp) -> None:
    session, c1a, _ = _two_book_session()
    dialog = ReviewWizardDialog(session)
    dialog.show()
    QApplication.processEvents()

    dialog._cards[1].clicked.emit(dialog._cards[1].candidate)
    QApplication.processEvents()
    decision = session.decision_for_current()
    assert decision is not None
    assert decision.candidate is not None
    assert decision.candidate.isbn13 == "9782222222222"
    assert dialog._cards[1].property("selected") is True
    assert dialog._cards[0].property("selected") is False

    dialog._cards[0].clicked.emit(c1a)
    QApplication.processEvents()
    assert session.decision_for_current().candidate == c1a
    dialog.close()


def test_wizard_preselects_single_very_high_candidate(qapp) -> None:
    only = _candidate("9784444444444", confidence_score=0.95)
    book = _book("Solo")
    session = ReviewSession.from_pairs([(book, _item(book, (only,)))])
    dialog = ReviewWizardDialog(session)
    dialog.show()
    QApplication.processEvents()

    assert session.has_decision_for_current()
    assert session.decision_for_current().candidate == only
    assert dialog._cards[0].property("selected") is True
    assert dialog._advance_timer.isActive() is False
    assert dialog.finish_button.isVisible() is True
    dialog.close()


def test_wizard_does_not_autoselect_when_not_very_high(qapp) -> None:
    only = _candidate("9785555555555", confidence_score=0.85)
    book = _book("Solo Medium")
    session = ReviewSession.from_pairs([(book, _item(book, (only,)))])
    dialog = ReviewWizardDialog(session)
    dialog.show()
    QApplication.processEvents()

    assert only.confidence_label == "High"
    assert not session.has_decision_for_current()
    dialog.close()


def test_wizard_save_preference_defaults_checked_and_toggleable(qapp) -> None:
    session, _, _ = _two_book_session()
    dialog = ReviewWizardDialog(session, save_updated_inventory=True)
    dialog.show()
    QApplication.processEvents()
    assert dialog.save_inventory_checkbox.isChecked() is True

    dialog.save_inventory_checkbox.setChecked(False)
    assert dialog.save_updated_inventory() is False
    dialog.close()

    session2, _, _ = _two_book_session()
    dialog2 = ReviewWizardDialog(session2, save_updated_inventory=False)
    dialog2.show()
    QApplication.processEvents()
    assert dialog2.save_inventory_checkbox.isChecked() is False
    dialog2.close()


def test_wizard_finish_seals_session_and_accepts(qapp) -> None:
    session, c1a, c2 = _two_book_session()
    dialog = ReviewWizardDialog(session, auto_advance_ms=0)
    dialog.show()
    QApplication.processEvents()
    dialog._cards[0].clicked.emit(c1a)
    QApplication.processEvents()
    assert dialog.progress_label.text() == "Book 2 of 2"
    dialog._cards[0].clicked.emit(c2)
    QApplication.processEvents()
    assert dialog.finish_button.isVisible() is True
    dialog.finish_button.click()
    QApplication.processEvents()

    assert session.is_finished()
    assert dialog.result() == dialog.DialogCode.Accepted


def test_controller_runs_wizard_and_applies_review(qapp, tmp_path: Path) -> None:
    book = _book("Needs Review")
    candidate = _candidate("9786666666666", confidence_score=0.93)
    item = _item(book, (candidate,))
    generation_result = WorkbookGenerationResult(
        books_imported=1,
        books_processed=1,
        labels_created=1,
        pages_created=1,
        barcodes_generated=1,
        output_path=tmp_path / "out.xlsx",
        enrichment=EnrichmentSummary(
            enabled=True,
            books_looked_up=1,
            ambiguous_matches=1,
            review_items=(item,),
        ),
    )

    class _Service:
        def __init__(self, settings) -> None:
            self.settings = settings

        def generate(self, **kwargs: object) -> WorkbookGenerationResult:
            return generation_result

    outcomes: list[ReviewWizardOutcome] = []

    def runner(session: ReviewSession, save_pref: bool) -> ReviewWizardOutcome:
        session.select_candidate(candidate)
        session.finish()
        review_result = BookReviewService().apply(session)
        outcome = ReviewWizardOutcome(
            session=session,
            save_updated_inventory=False,
            review_result=review_result,
        )
        outcomes.append(outcome)
        return outcome

    window = MainWindow()
    prefs = tmp_path / "prefs.json"
    controller = GuiController(
        window,
        generation_service_factory=_Service,
        preferences_path=prefs,
        review_wizard_runner=runner,
    )
    (tmp_path / "barcodes").mkdir()
    (tmp_path / "inventory.xlsx").write_text("x", encoding="utf-8")
    controller._state = (
        controller._state.with_inventory_workbook(tmp_path / "inventory.xlsx")
        .with_barcode_folder(tmp_path / "barcodes")
        .with_output_workbook(tmp_path / "out.xlsx")
    )
    controller._refresh_ui()
    controller.on_generate_labels()
    wait_until_generation_finished(controller)

    assert len(outcomes) == 1
    assert outcomes[0].review_result.resolved_count == 1
    assert controller._last_review_result is not None
    assert controller._last_review_result.resolved_count == 1
    assert controller._save_updated_inventory_on_review is False
    loaded = load_gui_preferences(path=prefs)
    assert loaded.save_updated_inventory_on_review is False
    window.close()


def test_controller_skips_wizard_when_no_review_items(
    qapp, tmp_path: Path
) -> None:
    generation_result = WorkbookGenerationResult(
        books_imported=1,
        books_processed=1,
        labels_created=1,
        pages_created=1,
        barcodes_generated=1,
        output_path=tmp_path / "out.xlsx",
        enrichment=EnrichmentSummary(enabled=True, isbns_found=1),
    )

    class _Service:
        def __init__(self, settings) -> None:
            self.settings = settings

        def generate(self, **kwargs: object) -> WorkbookGenerationResult:
            return generation_result

    called = {"count": 0}

    def runner(session: ReviewSession, save_pref: bool) -> ReviewWizardOutcome | None:
        called["count"] += 1
        return None

    window = MainWindow()
    controller = GuiController(
        window,
        generation_service_factory=_Service,
        preferences_path=tmp_path / "prefs.json",
        review_wizard_runner=runner,
    )
    (tmp_path / "barcodes").mkdir()
    (tmp_path / "inv.xlsx").write_text("x", encoding="utf-8")
    controller._state = (
        controller._state.with_inventory_workbook(tmp_path / "inv.xlsx")
        .with_barcode_folder(tmp_path / "barcodes")
        .with_output_workbook(tmp_path / "out.xlsx")
    )
    controller._refresh_ui()
    controller.on_generate_labels()
    wait_until_generation_finished(controller)
    assert called["count"] == 0
    window.close()




def test_controller_skips_inventory_write_when_unchecked(
    qapp, tmp_path: Path
) -> None:
    book = _book("Needs Review")
    candidate = _candidate("9786666666666", confidence_score=0.93)
    item = _item(book, (candidate,))
    generation_result = WorkbookGenerationResult(
        books_imported=1,
        books_processed=1,
        labels_created=1,
        pages_created=1,
        barcodes_generated=1,
        output_path=tmp_path / "Library Labels.xlsx",
        enrichment=EnrichmentSummary(
            enabled=True,
            books_looked_up=1,
            ambiguous_matches=1,
            review_items=(item,),
        ),
        books=(book,),
        source_rows=(2,),
    )

    class _Service:
        def __init__(self, settings) -> None:
            self.settings = settings

        def generate(self, **kwargs: object) -> WorkbookGenerationResult:
            return generation_result

    def runner(session: ReviewSession, save_pref: bool) -> ReviewWizardOutcome:
        session.select_candidate(candidate)
        session.finish()
        return ReviewWizardOutcome(
            session=session,
            save_updated_inventory=False,
            review_result=BookReviewService().apply(session),
        )

    class _FailingInventory:
        def write_updated_inventory(self, **kwargs: object) -> Path:
            raise AssertionError("inventory should not be written")

    window = MainWindow()
    prefs = tmp_path / "prefs.json"
    controller = GuiController(
        window,
        generation_service_factory=_Service,
        preferences_path=prefs,
        review_wizard_runner=runner,
        inventory_update_service=_FailingInventory(),  # type: ignore[arg-type]
    )
    (tmp_path / "barcodes").mkdir()
    inventory = tmp_path / "inventory.xlsx"
    inventory.write_text("x", encoding="utf-8")
    controller._state = (
        controller._state.with_inventory_workbook(inventory)
        .with_barcode_folder(tmp_path / "barcodes")
        .with_output_workbook(tmp_path / "Library Labels.xlsx")
    )
    controller._refresh_ui()
    controller.on_generate_labels()
    wait_until_generation_finished(controller)
    assert controller._last_updated_inventory_path is None
    assert window.is_showing_completion()
    assert window.completion_view.inventory_file_block.isHidden()
    window.close()


def test_gui_completion_includes_updated_inventory_summary() -> None:
    from classroom_library_label_maker.generation_summary import gui_completion_status

    result = WorkbookGenerationResult(
        books_imported=1,
        books_processed=1,
        labels_created=1,
        pages_created=1,
        barcodes_generated=1,
        output_path=Path("Library Labels.xlsx"),
    )
    text = gui_completion_status(
        result,
        updated_inventory_path=Path("Inventory (Updated ISBNs).xlsx"),
    )
    assert "Generation Complete" in text
    assert "✓ Label workbook created" in text
    assert "✓ Inventory workbook updated" in text
    assert "Library Labels.xlsx" in text
    assert "Inventory (Updated ISBNs).xlsx" in text


def test_gui_preferences_round_trip_save_inventory_flag(tmp_path: Path) -> None:
    path = tmp_path / "gui_preferences.json"
    save_gui_preferences(
        GuiPreferences(save_updated_inventory_on_review=False),
        path=path,
    )
    loaded = load_gui_preferences(path=path)
    assert loaded.save_updated_inventory_on_review is False
