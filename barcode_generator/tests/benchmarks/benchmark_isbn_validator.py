"""Engineering benchmarks for :class:`IsbnValidator`.

This module is **not** part of the normal unit-test suite.

Purpose
-------
Measure wall-clock time for ``normalize``, ``validate``, and ``validate_many``
at approximately 100 / 1,000 / 10,000 ISBN operations so developers can spot
accidental performance regressions during refactors.

What this is not
----------------
* Not a CI gate — timings must never fail continuous integration.
* Not an SLA — absolute numbers vary by machine and load.
* Not a correctness test — no functional assertions are made.

How to run
----------
From the ``barcode_generator`` directory::

    python tests/benchmarks/benchmark_isbn_validator.py

Optional (explicit path only; not collected by default ``pytest``)::

    python -m pytest tests/benchmarks/benchmark_isbn_validator.py -v -s

Interpretation
--------------
Compare relative timings on the same machine before and after a change.
Investigate order-of-magnitude regressions; ignore small run-to-run noise.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
import time

from classroom_library_label_maker.services.isbn_validator import IsbnValidator

# Mix of valid, hyphenated, and invalid inputs to exercise typical paths.
_SAMPLE_RAW: tuple[str | None, ...] = (
    "9780064400558",
    "978-0-06-440055-8",
    "978 006 440055 8",
    "9780060256654",
    "9780064400550",  # invalid checksum
    "978006440055",  # invalid length
    "9771234567896",  # invalid prefix (may also fail checksum)
    "978006440055X",  # non-numeric
    None,
    "   ",
)

_BATCH_SIZES: tuple[int, ...] = (100, 1_000, 10_000)


def _build_batch(size: int) -> list[str | None]:
    """Return ``size`` sample ISBN values cycling through ``_SAMPLE_RAW``."""
    samples = _SAMPLE_RAW
    return [samples[index % len(samples)] for index in range(size)]


def _time_call(label: str, size: int, action: Callable[[], object]) -> float:
    """Run ``action`` once and print elapsed milliseconds; return seconds."""
    started = time.perf_counter()
    action()
    elapsed = time.perf_counter() - started
    print(f"{label:18} n={size:>6,}  {elapsed * 1000:10.3f} ms")
    return elapsed


def run_benchmarks(sizes: Sequence[int] = _BATCH_SIZES) -> None:
    """Print timing information for normalize / validate / validate_many."""
    validator = IsbnValidator()
    print("IsbnValidator engineering benchmarks")
    print("(timing only — no assertions; not for CI)")
    print("-" * 48)

    for size in sizes:
        batch = _build_batch(size)

        _time_call(
            "normalize()",
            size,
            lambda b=batch: [validator.normalize(value) for value in b],
        )
        _time_call(
            "validate()",
            size,
            lambda b=batch: [validator.validate(value) for value in b],
        )
        _time_call(
            "validate_many()",
            size,
            lambda b=batch: validator.validate_many(b),
        )
        print("-" * 48)


def main() -> None:
    """CLI entry point for manual benchmark runs."""
    run_benchmarks()


if __name__ == "__main__":
    main()
