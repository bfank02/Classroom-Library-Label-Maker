"""Session-scoped dirty tracking for editable Home controls.

Editable widgets own their in-progress values until the controller commits
them (editing finished, generation starts, or an intentional reset). Dirty
flags prevent ``_refresh_ui`` sync helpers from overwriting those drafts with
previously loaded :class:`~classroom_library_label_maker.gui.form_state.GenerationFormState`
values.

This is an implementation detail only — no unsaved-changes UI.
"""

from __future__ import annotations

# Stable field keys for :class:`DirtyFieldTracker`.
FIELD_LABEL_FILENAME = "label_filename"


class DirtyFieldTracker:
    """Generic dirty-state set for editable Home fields."""

    __slots__ = ("_dirty",)

    def __init__(self) -> None:
        self._dirty: set[str] = set()

    def mark(self, field: str) -> None:
        """Mark ``field`` dirty for the current editing session."""
        self._dirty.add(field)

    def clear(self, field: str | None = None) -> None:
        """Clear one field, or all fields when ``field`` is ``None``."""
        if field is None:
            self._dirty.clear()
            return
        self._dirty.discard(field)

    def is_dirty(self, field: str) -> bool:
        """Return whether ``field`` has unsynced user edits."""
        return field in self._dirty

    def any_dirty(self) -> bool:
        """Return whether any editable field is dirty."""
        return bool(self._dirty)
