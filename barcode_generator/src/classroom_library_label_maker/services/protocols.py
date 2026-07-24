"""Protocols for optional enrichment services.

Implementations will live under ``services.lookups`` and ``services.covers``
when those features are built.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from classroom_library_label_maker.models import CoverImageResult, IsbnLookupResult


class IsbnLookupService(Protocol):
    """Protocol for future ISBN metadata lookup providers."""

    def lookup(self, isbn: str) -> IsbnLookupResult:
        """Look up metadata for an ISBN.

        Args:
            isbn: Normalized ISBN.

        Returns:
            Lookup result with any available metadata.
        """
        ...


class CoverDownloadService(Protocol):
    """Protocol for future cover image download providers."""

    def download(self, isbn: str, output_dir: Path) -> CoverImageResult:
        """Download a cover image for an ISBN.

        Args:
            isbn: Normalized ISBN.
            output_dir: Directory for cover image files.

        Returns:
            Result describing the downloaded (or failed) cover.
        """
        ...
