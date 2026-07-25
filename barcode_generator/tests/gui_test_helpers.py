"""Helpers for waiting on background GUI generation in tests."""

from __future__ import annotations

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from classroom_library_label_maker.gui.controller import GuiController


def wait_until_generation_finished(
    controller: GuiController,
    *,
    timeout_ms: int = 10_000,
) -> None:
    """Process Qt events until ``controller.is_generating`` is False."""
    waited = 0
    while controller.is_generating and waited < timeout_ms:
        QApplication.processEvents()
        QTest.qWait(20)
        waited += 20
    assert not controller.is_generating, "generation did not finish in time"
