"""Engineering benchmark for catalog enrichment (Teacher Demo Library).

This module is **not** part of the normal unit-test suite.

Purpose
-------
Measure enrichment throughput against ``samples/Teacher Demo Library.xlsx``
and report Google Books vs Open Library contribution. Reports counts and
timings only — never prints API keys.

What this is not
----------------
* Not a CI gate — timings must never fail continuous integration.
* Not an SLA — absolute numbers vary by machine, network, and quota.
* Not a correctness test — no functional assertions are made.

How to run
----------
From the repository root (requires network + optional ``GOOGLE_BOOKS_API_KEY``)::

    cd barcode_generator
    python tests/benchmarks/benchmark_google_books_enrichment.py

Optional workbook override::

    python tests/benchmarks/benchmark_google_books_enrichment.py /path/to.xlsx
"""

from __future__ import annotations

from pathlib import Path
import sys
import time

from classroom_library_label_maker.config import (
    load_application_settings,
    load_google_books_auth_config,
    log_google_books_authentication_status,
)
from classroom_library_label_maker.logger import setup_logging
from classroom_library_label_maker.models import BookEnrichmentStatus
from classroom_library_label_maker.services.book_enrichment_service import (
    book_needs_isbn_lookup,
    create_default_enrichment_service,
)
from classroom_library_label_maker.services.excel_import_service import (
    ExcelImportService,
)
from classroom_library_label_maker.services.lookups.composite import (
    CompositeBookEnrichmentProvider,
)
from classroom_library_label_maker.services.lookups.google_books import (
    GoogleBooksEnrichmentProvider,
)
from classroom_library_label_maker.services.lookups.open_library import (
    OpenLibraryEnrichmentProvider,
)


def _default_demo_workbook() -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "samples" / "Teacher Demo Library.xlsx"


def run_benchmark(workbook_path: Path) -> None:
    """Import the demo workbook and enrich missing ISBNs via the default pipeline."""
    setup_logging(level="INFO")
    auth = load_google_books_auth_config()
    log_google_books_authentication_status(auth.status)

    settings = load_application_settings(
        workbook_path=workbook_path,
        lookup_missing_isbns=True,
    )
    importer = ExcelImportService(settings)
    imported = importer.import_books(workbook_path)
    books = list(imported.books)
    missing = [book for book in books if book_needs_isbn_lookup(book)]

    enrichment = create_default_enrichment_service(
        api_key=settings.google_books_api_key,
    )
    outer = enrichment.provider
    if not isinstance(outer, CompositeBookEnrichmentProvider):
        raise TypeError("Expected CompositeBookEnrichmentProvider")
    google = outer.providers[0]
    open_library = outer.providers[1]
    if not isinstance(google, GoogleBooksEnrichmentProvider):
        raise TypeError("Expected GoogleBooksEnrichmentProvider first")
    if not isinstance(open_library, OpenLibraryEnrichmentProvider):
        raise TypeError("Expected OpenLibraryEnrichmentProvider second")

    print("Catalog enrichment engineering benchmark")
    print("(timing only — no assertions; not for CI)")
    print("-" * 56)
    print(f"workbook:              {workbook_path}")
    print(f"authentication:        {'Enabled' if auth.is_enabled else 'Anonymous'}")
    print(f"total books:           {len(books)}")
    print(f"missing ISBNs:         {len(missing)}")
    print(f"Google pacing (s):     {google.min_request_interval_seconds:.2f}")
    print(f"Open Library pacing:   {open_library.min_request_interval_seconds:.2f}")
    print("-" * 56)

    google_found = 0
    google_ambiguous = 0
    google_not_found = 0
    ol_recovered_found = 0
    ol_recovered_ambiguous = 0
    still_not_found = 0
    errors = 0

    started = time.perf_counter()
    for book in missing:
        result = enrichment.enrich(book)
        provider = result.provider_name or ""
        if result.status is BookEnrichmentStatus.FOUND:
            if provider == "Google Books":
                google_found += 1
            elif provider == "Open Library":
                ol_recovered_found += 1
                google_not_found += 1
            else:
                google_found += 1
        elif result.status is BookEnrichmentStatus.AMBIGUOUS:
            if provider == "Google Books":
                google_ambiguous += 1
            elif provider == "Open Library":
                ol_recovered_ambiguous += 1
                google_not_found += 1
            else:
                google_ambiguous += 1
        elif result.status is BookEnrichmentStatus.NOT_FOUND:
            still_not_found += 1
            google_not_found += 1
        else:
            errors += 1
            google_not_found += 1
    elapsed = time.perf_counter() - started

    ol_still_not_found = still_not_found
    auto_resolved = google_found + ol_recovered_found
    manual_review = google_ambiguous + ol_recovered_ambiguous
    google_contribution = google_found + google_ambiguous
    open_library_contribution = ol_recovered_found + ol_recovered_ambiguous

    lookups = len(missing)
    avg = (elapsed / lookups) if lookups else 0.0
    print("Google Books")
    print(f"  FOUND:               {google_found}")
    print(f"  AMBIGUOUS:           {google_ambiguous}")
    print(f"  NOT_FOUND:           {google_not_found}")
    print("Open Library")
    print(f"  Recovered books:     {ol_recovered_found}")
    print(f"  Recovered ambiguities:{ol_recovered_ambiguous}")
    print(f"  Recovered NOT_FOUND: {ol_still_not_found}")
    print("Final totals")
    print(f"  Automatically resolved: {auto_resolved}")
    print(f"  Manual review:          {manual_review}")
    print(f"  Still not found:        {still_not_found}")
    if errors:
        print(f"  Errors:                 {errors}")
    print("Provider contribution")
    print(f"  Google Books:        {google_contribution}")
    print(f"  Open Library:        {open_library_contribution}")
    print("-" * 56)
    print(f"Google Books requests: {google.request_count}")
    print(f"Open Library requests: {open_library.request_count}")
    print(f"cache hits:            {enrichment.cache_hits}")
    print(f"cache misses:          {enrichment.cache_misses}")
    print(f"retries (429):         {google.retry_count}")
    print(f"HTTP 429 responses:    {google.rate_limit_response_count}")
    print(f"total enrichment time: {elapsed:.2f} s")
    print(f"average lookup time:   {avg:.2f} s")
    print("-" * 56)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    workbook = Path(args[0]) if args else _default_demo_workbook()
    if not workbook.is_file():
        print(f"error: workbook not found: {workbook}", file=sys.stderr)
        return 1
    run_benchmark(workbook)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
