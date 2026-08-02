"""Presentation tests for Home / Ready to Print visual accessibility (v1.4.2)."""

from __future__ import annotations

import os

from PySide6.QtWidgets import QApplication, QGroupBox, QLabel
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from classroom_library_label_maker.generation_summary import (
    GuiCompletionSummary,
)
from classroom_library_label_maker.gui import theme
from classroom_library_label_maker.gui.app import create_application
from classroom_library_label_maker.gui.main_window import MainWindow
from classroom_library_label_maker.metadata import APP_NAME


@pytest.fixture(scope="module")
def qapp():
    app = create_application(
        ["classroom-library-label-maker-gui-visual-a11y"]
    )
    yield app


def test_theme_status_colors_are_distinct() -> None:
    assert theme.status_color("ok") == theme.COLOR_SUCCESS
    assert theme.status_color("warning") == theme.COLOR_WARNING
    assert theme.status_color("error") == theme.COLOR_ERROR
    assert len({theme.COLOR_SUCCESS, theme.COLOR_WARNING, theme.COLOR_ERROR}) == 3


def test_home_header_typography_hierarchy(qapp) -> None:
    window = MainWindow()
    window.show()
    QApplication.processEvents()

    title_ss = window.header_title_label.styleSheet()
    subtitle_ss = window.header_subtitle_label.styleSheet()
    assert theme.COLOR_HEADING in title_ss
    assert f"{theme.FONT_PRODUCT_TITLE_PX}px" in title_ss
    assert "font-weight: 700" in title_ss
    assert theme.COLOR_SECONDARY in subtitle_ss
    assert f"{theme.FONT_SUBTITLE_PX}px" in subtitle_ss
    # Product name must read larger / heavier than the tagline.
    assert theme.FONT_PRODUCT_TITLE_PX > theme.FONT_SUBTITLE_PX
    assert window.header_title_label.text() == APP_NAME
    assert window.header_subtitle_label.text()
    window.close()


def test_home_version_and_section_theme(qapp) -> None:
    window = MainWindow()
    window.show()
    QApplication.processEvents()

    assert theme.COLOR_MUTED in window.version_label.styleSheet()
    assert theme.COLOR_HEADING in window.home_page.styleSheet()
    for name in ("filesGroup", "optionsGroup", "actionsGroup"):
        group = window.findChild(QGroupBox, name)
        assert group is not None
        assert group.accessibleName()
    window.close()


def test_home_and_completion_share_page_margins(qapp) -> None:
    window = MainWindow()
    window.show()
    QApplication.processEvents()

    home_margins = window.home_page.layout().contentsMargins()
    completion_margins = window.completion_view.layout().contentsMargins()
    assert home_margins.left() == theme.PAGE_MARGIN_H
    assert completion_margins.left() == theme.PAGE_MARGIN_H
    assert home_margins.top() == theme.PAGE_MARGIN_TOP
    assert completion_margins.top() == theme.PAGE_MARGIN_TOP
    window.close()


def test_completion_section_order_and_typography(qapp) -> None:
    window = MainWindow()
    view = window.completion_view
    window.show_completion()
    window.show()
    QApplication.processEvents()

    caption = view.findChild(QLabel, "completionFilesCaption")
    assert caption is not None
    assert caption.text() == "Files Created"

    # Vertical order: headline → details → Files Created → label file → actions.
    assert view.headline_label.y() < view.details_label.y()
    assert view.details_label.y() < caption.y()
    assert caption.y() < view.label_file_block.y()
    assert view.label_file_block.y() < view.done_button.y()

    headline_ss = view.headline_label.styleSheet()
    assert theme.COLOR_SUCCESS in headline_ss
    assert f"{theme.FONT_PAGE_HEADLINE_PX}px" in headline_ss
    assert theme.COLOR_BODY in view.details_label.styleSheet()
    assert theme.COLOR_SECONDARY in caption.styleSheet()
    assert theme.COLOR_HEADING in view.label_file_heading.styleSheet()
    assert theme.COLOR_FILENAME in view.label_file_name.styleSheet()
    # Headline larger than body / captions.
    assert theme.FONT_PAGE_HEADLINE_PX > theme.FONT_BODY_PX
    assert theme.FONT_PAGE_HEADLINE_PX > theme.FONT_SECTION_CAPTION_PX
    window.close()


def test_completion_attention_headline_uses_warning_color(qapp) -> None:
    window = MainWindow()
    view = window.completion_view
    summary = GuiCompletionSummary(
        headline="✔ Ready to Print",
        detail_lines=("1 labels created", "Review before printing."),
        label_workbook_name="labels.xlsx",
        label_workbook_path=None,
        updated_inventory_name=None,
        updated_inventory_path=None,
        requires_attention=True,
    )
    view.populate(summary)
    QApplication.processEvents()
    assert theme.COLOR_WARNING in view.headline_label.styleSheet()
    assert theme.COLOR_SUCCESS not in view.headline_label.styleSheet()
    window.close()


def test_completion_accessibility_metadata(qapp) -> None:
    window = MainWindow()
    view = window.completion_view
    window.show()
    QApplication.processEvents()

    assert view.accessibleName() == "Ready to Print"
    assert view.headline_label.accessibleName() == "Ready to Print"
    assert view.details_label.accessibleName() == "Generation summary"
    assert view.label_file_name.accessibleName() == "Label workbook file name"
    assert view.open_label_button.accessibleName() == "Open Label Workbook"
    assert view.done_button.accessibleName() == "Done"
    assert view.done_button.isDefault()
    window.close()
