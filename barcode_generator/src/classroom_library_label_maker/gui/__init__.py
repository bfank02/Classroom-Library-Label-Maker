"""Desktop GUI presentation layer (PySide6).

This package is a thin adapter over the workbook generation engine. Business
logic stays in ``services/``; widgets and dialogs stay here.

Importing this package does **not** create a ``QApplication`` or open a window.
Call :func:`main` (or ``python -m classroom_library_label_maker.gui``) to start
the desktop application.
"""

from __future__ import annotations

__all__ = [
    "main",
]


def main(argv: list[str] | None = None) -> int:
    """Launch the desktop application and run the Qt event loop.

    Args:
        argv: Optional argument list (defaults to ``sys.argv`` for Qt).

    Returns:
        Process exit code from ``QApplication.exec()``.
    """
    # Lazy import so ``import classroom_library_label_maker.gui`` stays light
    # and free of Qt side effects until launch.
    from classroom_library_label_maker.gui.app import run

    return run(argv)
