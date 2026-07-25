# Public API

Public surface of the **Classroom Library Label Maker** barcode generator
package (`classroom_library_label_maker`).

Prefer importing from documented submodules
(`models`, `services`, `rendering`, `exceptions`, `config`, `metadata`).
The package root re-exports a narrow set of common types.

## Stability legend

| Label | Meaning |
|-------|---------|
| **Stable** | Intended for consumption by future features (Excel, CLI, labels). Backward-compatible unless a major version bump. |
| **Experimental** | Usable, but shape may change as adjacent features land. |
| **Internal** | Infrastructure or transitional API. Prefer not to depend on it from new call sites. |

---

## Domain Models

Module: `classroom_library_label_maker.models`

### `Book` — Stable — External

**Purpose:** Classroom library book record passed into validation, generation,
and batch orchestration.

**Public methods**

| Method | Inputs | Outputs |
|--------|--------|---------|
| `from_dict(data)` | JSON-like mapping (`isbn` or legacy `isbn13`, `title`, `author`, …) | `Book` |
| `to_dict()` | — | JSON-compatible `dict` |

**Fields (inputs/outputs):** `isbn`, `title`, `author`, `copies`, optional
`genre`, `reading_level`, `location`, `condition`.

### `ValidationResult` — Stable — External

**Purpose:** Outcome of validating one ISBN (never raises for expected invalid
input).

**Fields:** `isbn`, `is_valid`, `errors`, `error_code`.

### `ValidationErrorCode` — Stable — External

**Purpose:** Machine-readable ISBN failure codes; `.message` is the default
user-facing text.

### `BarcodeStatus` — Stable — External

**Purpose:** Outcome enum for a single barcode generation attempt
(`GENERATED`, `ALREADY_EXISTS`, `INVALID_ISBN`, `ERROR`, `SKIPPED`).

### `BarcodeGenerationResult` — Stable — External

**Purpose:** Result of generating (or skipping) one barcode image.

**Public methods:** `to_dict()`.

**Fields:** `isbn`, `status`, `output_path`, `message`, `title`.

### `BookProcessingStatus` — Stable — External

**Purpose:** Per-book status inside a batch (`GENERATED`, `ALREADY_EXISTS`,
`VALIDATION_FAILED`, `GENERATION_FAILED`).

### `BookProcessingResult` — Stable — External

**Purpose:** Combined validation + generation outcome for one book in a batch.

**Public methods:** `to_dict()`.

**Fields:** `isbn`, `title`, `status`, `output_path`, `message`, optional
`validation`, `generation`.

### `BatchProcessingResult` — Stable — External

**Purpose:** Aggregate batch outcome (ordered results + timing + counts).

**Derived properties:** `total_processed`, `successful_generations`,
`existing_barcodes_skipped`, `validation_failures`, `generation_failures`,
`books_per_second` (safe on zero elapsed time).

**Public methods:** `to_dict()`.

**Fields:** `results` (input order), `elapsed_seconds`.

### `ApplicationSettings` — Stable — External

**Purpose:** Project paths, logging, and barcode render geometry for a run.

**Construction:** Prefer `config.load_application_settings(...)`.

**Notable fields:** `barcode_output_directory`, `log_directory`,
`barcode_module_width` / `height` / `quiet_zone` / `font_size` / `dpi`,
optional `input_path` / `results_path`.

### `BatchResults` — Experimental — External (legacy CLI)

**Purpose:** Older aggregate used by `BatchProcessor.write_results`. Prefer
`BatchProcessingResult` for new orchestration.

### `IsbnLookupResult` / `CoverImageResult` — Experimental — External

**Purpose:** Reserved result shapes for future enrichment providers.

---

## Validation

Module: `classroom_library_label_maker.services.isbn_validator`

### `IsbnValidator` (alias `ISBNValidator`) — Stable — External

**Purpose:** Normalize and validate ISBN-13 values. Stateless. Does not raise
for expected invalid ISBNs.

| Method | Stability | Inputs | Outputs |
|--------|-----------|--------|---------|
| `normalize(isbn)` | **Stable** | `str \| None` | Digits-only string (may be empty) |
| `validate(isbn)` | **Stable** | `str \| None` | `ValidationResult` |
| `validate_many(isbns)` | **Stable** | iterable of `str \| None` | `list[ValidationResult]` (order preserved) |
| `is_valid(isbn)` | Experimental | `str \| None` | `bool` |
| `compute_check_digit(first_twelve_digits)` | Experimental | 12-digit string | Check digit `str` (may raise `ValueError`) |

---

## Barcode Generation

Module: `classroom_library_label_maker.services.barcode_generation_service`

### `BarcodeGenerationService` — Stable — External

**Purpose:** Create EAN-13 PNG files for a **validated** `Book`. Does not
re-validate ISBNs. Does not import third-party barcode libraries directly.

| Method | Inputs | Outputs / errors |
|--------|--------|------------------|
| `__init__(settings, *, renderer=None, …)` | `ApplicationSettings`; optional `BarcodeRenderer` | service |
| `generate_for_book(book)` | Validated `Book` | `BarcodeGenerationResult` (`GENERATED` or `ALREADY_EXISTS`); may raise `FileSystemError` / `BarcodeGenerationError` |
| `output_path_for(isbn)` | Normalized ISBN stem | `Path` to `{dir}/{isbn}.png` |

**External use:** Yes — primary generation API for all future features.

---

## Batch Processing

Module: `classroom_library_label_maker.services.batch_processing_service`

### `BatchProcessingService` — Stable — External

**Purpose:** Orchestrate validation + generation over a collection of books.
Continues after per-book failures. Preserves input order.

| Method | Inputs | Outputs |
|--------|--------|---------|
| `__init__(settings, *, validator=None, generator=None, progress_reporter=None, cancellation_token=None)` | Settings + optional overrides / hooks | service |
| `process_books(books)` | `Sequence[Book]` (may be empty) | `BatchProcessingResult` |

**Notes**

- `progress_reporter`: optional; see Protocols.
- `cancellation_token`: accepted for API stability; **not enforced** yet.

**External use:** Yes — orchestration layer for future Excel import.

---

## Rendering

Module: `classroom_library_label_maker.rendering`

### `BarcodeRenderer` — Stable — External (protocol)

**Purpose:** Library-agnostic contract for writing barcode images.

| Method | Inputs | Outputs |
|--------|--------|---------|
| `render_to_file(data, output_path, *, symbology=EAN13)` | Payload string, destination path, symbology | `Path` written |

### `BarcodeSymbology` — Stable — External

**Purpose:** Symbology identifiers. `EAN13` implemented; `CODE128` / `QR`
reserved.

### `PythonBarcodeRenderer` — Stable — External (default backend)

**Purpose:** EAN-13 PNG backend via python-barcode + Pillow. Keeps vendor
types inside the rendering layer.

| Method | Inputs | Outputs |
|--------|--------|---------|
| `__init__(*, module_width, module_height, quiet_zone, font_size, dpi)` | Geometry (defaults from constants) | renderer |
| `from_settings(settings)` | `ApplicationSettings` | renderer |
| `render_to_file(...)` | Same as protocol | `Path`; may raise `ValueError` / `OSError` |

**External use:** Prefer depending on `BarcodeRenderer` in services; construct
`PythonBarcodeRenderer` only when injecting a concrete backend.

---

## Services

Package: `classroom_library_label_maker.services`

| Type | Stability | Audience | Purpose |
|------|-----------|----------|---------|
| `IsbnValidator` | Stable | External | ISBN validation |
| `BarcodeGenerationService` | Stable | External | Single-book PNG generation |
| `BatchProcessingService` | Stable | External | Multi-book orchestration |
| `BatchProcessor` | Experimental | Internal / transitional | CLI/JSON adapter (`load_books` still stubbed) |
| `BarcodeGenerator` | Internal | Transitional | Legacy path helpers; superseded by `BarcodeGenerationService` |

---

## Protocols

Module: `classroom_library_label_maker.services.protocols`

### `BatchProgressReporter` — Stable — External

**Purpose:** Optional progress hooks for CLI/UI without changing
`process_books()`.

| Method | Inputs |
|--------|--------|
| `on_batch_started(total)` | Book count |
| `on_book_processed(index, total, result)` | 1-based index + `BookProcessingResult` |
| `on_batch_completed(total)` | Book count |

### `BatchCancellationToken` — Experimental — External

**Purpose:** Cooperative cancellation extension point.

| Method | Outputs |
|--------|---------|
| `is_cancellation_requested()` | `bool` |

**Status:** Accepted by `BatchProcessingService` but **not enforced** yet.

### `IsbnLookupService` / `CoverDownloadService` — Experimental — External

**Purpose:** Future enrichment contracts (`lookup`, `download`).

---

## Exceptions

Module: `classroom_library_label_maker.exceptions` — Stable — External

```
ApplicationError
├── ConfigurationError
├── ValidationError
│   ├── InvalidISBNError
│   └── InvalidWorkbookError
├── BarcodeGenerationError
└── FileSystemError
```

Use these for unexpected failures. Expected invalid ISBNs use
`ValidationResult`, not exceptions.

---

## Related docs

- [Architecture](Architecture.md)
- [Developer Review Checklist](DeveloperReviewChecklist.md)
- [Feature Review Template](templates/FeatureReviewTemplate.md)
- [FDR-002 Barcode Generation](decisions/FDR-002-barcode-generation.md)
