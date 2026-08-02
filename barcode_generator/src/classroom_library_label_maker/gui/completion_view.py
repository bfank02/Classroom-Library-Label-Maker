"""Ready to Print completion view — final page of the generation workflow.

Presentation only. Summary text and paths come from
:class:`~classroom_library_label_maker.generation_summary.GuiCompletionSummary`.
Typography and colors come from :mod:`classroom_library_label_maker.gui.theme`.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from classroom_library_label_maker.generation_summary import GuiCompletionSummary
from classroom_library_label_maker.gui import theme


class CompletionView(QWidget):
    """Full-page completion experience shown after successful generation."""

    open_label_workbook_requested = Signal()
    open_updated_inventory_requested = Signal()
    done_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("completionView")
        self.setAccessibleName("Ready to Print")
        self.setAccessibleDescription(
            "Generation finished. Open created files or return to the home screen."
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(
            theme.PAGE_MARGIN_H,
            theme.PAGE_MARGIN_TOP,
            theme.PAGE_MARGIN_H,
            theme.PAGE_MARGIN_BOTTOM,
        )
        root.setSpacing(theme.PAGE_SECTION_SPACING)

        root.addStretch(1)

        # Hierarchy: success headline → explanation → Files Created → actions.
        self.headline_label = QLabel("✔ Ready to Print")
        self.headline_label.setObjectName("completionHeadline")
        self.headline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.headline_label.setStyleSheet(theme.completion_headline_stylesheet())
        self.headline_label.setAccessibleName("Ready to Print")
        root.addWidget(self.headline_label)

        self.details_label = QLabel()
        self.details_label.setObjectName("completionDetails")
        self.details_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.details_label.setWordWrap(True)
        self.details_label.setStyleSheet(theme.completion_details_stylesheet())
        self.details_label.setAccessibleName("Generation summary")
        root.addWidget(self.details_label)

        files_caption = QLabel("Files Created")
        files_caption.setObjectName("completionFilesCaption")
        files_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        files_caption.setStyleSheet(theme.completion_files_caption_stylesheet())
        files_caption.setAccessibleName("Files Created")
        root.addWidget(files_caption)

        self.label_file_block = QWidget()
        self.label_file_block.setObjectName("completionLabelFileBlock")
        label_layout = QVBoxLayout(self.label_file_block)
        label_layout.setContentsMargins(0, 6, 0, 6)
        label_layout.setSpacing(4)
        self.label_file_heading = QLabel("✓ Label Workbook")
        self.label_file_heading.setObjectName("completionLabelFileHeading")
        self.label_file_heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_file_heading.setStyleSheet(
            theme.completion_file_heading_stylesheet()
        )
        self.label_file_name = QLabel()
        self.label_file_name.setObjectName("completionLabelFileName")
        self.label_file_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_file_name.setWordWrap(True)
        self.label_file_name.setStyleSheet(theme.completion_filename_stylesheet())
        self.label_file_name.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.label_file_name.setAccessibleName("Label workbook file name")
        label_layout.addWidget(self.label_file_heading)
        label_layout.addWidget(self.label_file_name)
        root.addWidget(self.label_file_block)

        self.inventory_file_block = QWidget()
        self.inventory_file_block.setObjectName("completionInventoryFileBlock")
        inv_layout = QVBoxLayout(self.inventory_file_block)
        inv_layout.setContentsMargins(0, 6, 0, 6)
        inv_layout.setSpacing(4)
        self.inventory_file_heading = QLabel("✓ Updated Inventory")
        self.inventory_file_heading.setObjectName("completionInventoryFileHeading")
        self.inventory_file_heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.inventory_file_heading.setStyleSheet(
            theme.completion_file_heading_stylesheet()
        )
        self.inventory_file_name = QLabel()
        self.inventory_file_name.setObjectName("completionInventoryFileName")
        self.inventory_file_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.inventory_file_name.setWordWrap(True)
        self.inventory_file_name.setStyleSheet(
            theme.completion_filename_stylesheet()
        )
        self.inventory_file_name.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.inventory_file_name.setAccessibleName("Updated inventory file name")
        inv_layout.addWidget(self.inventory_file_heading)
        inv_layout.addWidget(self.inventory_file_name)
        self.inventory_file_block.hide()
        root.addWidget(self.inventory_file_block)

        root.addSpacing(16)

        actions = QHBoxLayout()
        actions.setObjectName("completionActionsRow")
        actions.setSpacing(12)
        actions.addStretch(1)

        self.open_label_button = QPushButton("Open Label Workbook")
        self.open_label_button.setObjectName("completionOpenLabelButton")
        self.open_label_button.setMinimumHeight(32)
        self.open_label_button.setAccessibleName("Open Label Workbook")
        self.open_label_button.setAccessibleDescription(
            "Open the generated label workbook with the default application"
        )
        self.open_label_button.setAutoDefault(False)
        self.open_label_button.clicked.connect(self.open_label_workbook_requested.emit)
        actions.addWidget(self.open_label_button)

        self.open_inventory_button = QPushButton("Open Updated Inventory")
        self.open_inventory_button.setObjectName("completionOpenInventoryButton")
        self.open_inventory_button.setMinimumHeight(32)
        self.open_inventory_button.setAccessibleName("Open Updated Inventory")
        self.open_inventory_button.setAccessibleDescription(
            "Open the updated inventory workbook with the default application"
        )
        self.open_inventory_button.setAutoDefault(False)
        self.open_inventory_button.clicked.connect(
            self.open_updated_inventory_requested.emit
        )
        self.open_inventory_button.hide()
        actions.addWidget(self.open_inventory_button)

        self.done_button = QPushButton("Done")
        self.done_button.setObjectName("completionDoneButton")
        self.done_button.setMinimumHeight(32)
        self.done_button.setMinimumWidth(96)
        self.done_button.setDefault(True)
        self.done_button.setAutoDefault(True)
        self.done_button.setAccessibleName("Done")
        self.done_button.setAccessibleDescription(
            "Return to the home screen to generate another label workbook"
        )
        self.done_button.clicked.connect(self.done_requested.emit)
        actions.addWidget(self.done_button)

        actions.addStretch(1)
        root.addLayout(actions)

        root.addStretch(2)

        self._summary: GuiCompletionSummary | None = None

    def summary(self) -> GuiCompletionSummary | None:
        """Return the summary currently displayed, if any."""
        return self._summary

    def populate(self, summary: GuiCompletionSummary) -> None:
        """Fill the view from a pre-built completion summary."""
        self._summary = summary
        self.headline_label.setText(summary.headline)
        self.details_label.setText("\n".join(summary.detail_lines))
        self.label_file_name.setText(summary.label_workbook_name)
        self.label_file_name.setToolTip(
            str(summary.label_workbook_path)
            if summary.label_workbook_path is not None
            else summary.label_workbook_name
        )
        has_label = summary.label_workbook_path is not None
        self.open_label_button.setEnabled(has_label)

        has_inventory = summary.updated_inventory_path is not None
        self.inventory_file_block.setVisible(has_inventory)
        self.open_inventory_button.setVisible(has_inventory)
        if has_inventory:
            assert summary.updated_inventory_name is not None
            self.inventory_file_name.setText(summary.updated_inventory_name)
            self.inventory_file_name.setToolTip(str(summary.updated_inventory_path))

        self.headline_label.setStyleSheet(
            theme.completion_headline_stylesheet(
                attention=summary.requires_attention
            )
        )
        self.done_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def clear(self) -> None:
        """Reset widgets for the next generation run."""
        self._summary = None
        self.details_label.clear()
        self.label_file_name.clear()
        self.label_file_name.setToolTip("")
        self.inventory_file_name.clear()
        self.inventory_file_name.setToolTip("")
        self.inventory_file_block.hide()
        self.open_inventory_button.hide()
        self.open_label_button.setEnabled(False)
        self.headline_label.setText("✔ Ready to Print")
        self.headline_label.setStyleSheet(theme.completion_headline_stylesheet())
