"""Filesystem helpers for reading and writing application artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def ensure_directory(path: Path) -> Path:
    """Create ``path`` (and parents) if it does not already exist.

    Args:
        path: Directory path to ensure.

    Returns:
        The same ``path`` for convenient chaining.
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path) -> Any:
    """Load and parse a JSON file.

    Args:
        path: Path to a UTF-8 JSON file.

    Returns:
        The deserialized JSON value (typically a ``dict`` or ``list``).

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        json.JSONDecodeError: If the file contents are not valid JSON.

    Note:
        Schema validation for books / results payloads will be added when
        ``BatchProcessor.load_books`` is implemented.
    """
    text = path.read_text(encoding="utf-8")
    return json.loads(text)


def write_json(path: Path, data: Any, *, indent: int = 2) -> None:
    """Serialize ``data`` to a UTF-8 JSON file, creating parents as needed.

    Args:
        path: Destination file path.
        data: JSON-serializable value.
        indent: Indent level passed to :func:`json.dumps`.
    """
    ensure_directory(path.parent)
    payload = json.dumps(data, indent=indent, ensure_ascii=False) + "\n"
    path.write_text(payload, encoding="utf-8")


def file_exists(path: Path) -> bool:
    """Return whether ``path`` exists and is a file.

    Args:
        path: Filesystem path to check.

    Returns:
        ``True`` if ``path`` is an existing file.
    """
    return path.is_file()
