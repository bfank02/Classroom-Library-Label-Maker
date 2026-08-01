"""Engineering benchmark for Google Books enrichment (Teacher Demo Library).

This module is **not** part of the normal unit-test suite.

Purpose
-------
Measure enrichment throughput against ``samples/Teacher Demo Library.xlsx``
so developers can tune authenticated vs anonymous pacing. Reports counts and
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
from classroom_library_label_maker.services.book_enrichment_service import (
    book_needs_isbn_lookup,
    create_default_enrichment_service,
)
from classroom_library_label_maker.services.excel_import_service import (
    ExcelImportService,
)
from classroom_library_label_maker.services.lookups.google_books import (
    GoogleBooksEnrichmentProvider,
)


def _default_demo_workbook() -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "samples" / "Teacher Demo Library.xlsx"


def run_benchmark(workbook_path: Path) -> None:
    """Import the demo workbook and enrich missing ISBNs with live Google Books."""
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
    provider = enrichment.provider
    if not isinstance(provider, GoogleBooksEnrichmentProvider):
        raise TypeError("Expected GoogleBooksEnrichmentProvider")

    print("Google Books enrichment engineering benchmark")
    print("(timing only — no assertions; not for CI)")
    print("-" * 56)
    print(f"workbook:              {workbook_path}")
    print(f"authentication:        {'Enabled' if auth.is_enabled else 'Anonymous'}")
    print(f"total books:           {len(books)}")
    print(f"missing ISBNs:         {len(missing)}")
    print(
        f"pacing interval (s):   {provider.min_request_interval_seconds:.2f}"
    )
    print("-" * 56)

    started = time.perf_counter()
    for book in missing:
        enrichment.enrich(book)
    elapsed = time.perf_counter() - started

    lookups = len(missing)
    avg = (elapsed / lookups) if lookups else 0.0
    print(f"Google Books requests: {provider.request_count}")
    print(f"cache hits:            {enrichment.cache_hits}")
    print(f"cache misses:          {enrichment.cache_misses}")
    print(f"retries (429):         {provider.retry_count}")
    print(f"HTTP 429 responses:    {provider.rate_limit_response_count}")
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
