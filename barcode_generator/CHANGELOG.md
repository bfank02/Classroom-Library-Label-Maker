# Changelog

All notable changes to the Classroom Library barcode generator are documented
in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Google Books API key integration: `GOOGLE_BOOKS_API_KEY` resolved once in
  `config.load_google_books_auth_config()`, stored on `ApplicationSettings`,
  injected into `GoogleBooksEnrichmentProvider` (provider never reads env)
- Startup authentication logging (`Enabled` / anonymous / invalid) with no
  network test request and no key leakage
- Authenticated pacing (~0.40s) vs anonymous (~1.25s), with 401/403 fallback
  to anonymous for the remainder of a run
- Developer enrichment benchmark:
  `tests/benchmarks/benchmark_google_books_enrichment.py`
- Book enrichment architecture: `BookEnrichmentService`,
  `BookEnrichmentProvider`, `NullBookEnrichmentProvider`, plus immutable
  `BookEnrichmentResult` / `BookEnrichmentStatus` (not wired into generation;
  Version 1.0 behavior unchanged)
- `GoogleBooksEnrichmentProvider`: title/author Google Books search with
  normalization, confidence scoring, and transport errors mapped to
  `BookEnrichmentResult` (optional inject; not used during generation)
- In-memory enrichment cache on `BookEnrichmentService` (normalized
  title+author key; all result statuses cached; discarded with the instance)
- Integrated ISBN enrichment during generation (`lookup_missing_isbns`,
  progress stage, GUI checkbox, `EnrichmentSummary` on
  `WorkbookGenerationResult`)
- Enrichment review details: immutable `ReviewItem` list on
  `EnrichmentSummary`, shown in GUI/CLI ISBN Lookup Summary (up to five
  titles) and generation logs
- Candidate preservation for future interactive review: immutable
  `ReviewCandidate` on ambiguous `BookEnrichmentResult` / `ReviewItem`
  (ordered by confidence; successful finds keep an empty candidate list;
  cached results reuse peers without extra Google Books requests)
- User-facing confidence bands on `ReviewCandidate`: internal
  `confidence_score` plus derived `confidence_label` (`Very High` /
  `High` / `Medium` / `Low`) via domain `confidence_label_for_score`
- Interactive review business layer: `ReviewSession`, immutable
  `ReviewDecision` / `ReviewSessionResult`, and `BookReviewService`
  (no GUI, no workbook writes, no extra catalog requests)
- Interactive review wizard (`ReviewWizardDialog`): thin Qt UI over
  `ReviewSession` after generation
- Updated inventory workbook after review: `InventoryUpdateService` +
  `OpenPyxlInventoryWorkbookUpdater` write `Inventory (Updated ISBNs).xlsx`
  (unique suffix on collision); original inventory never overwritten;
  completion summary lists both saved workbooks
- Cross-platform packaging: shared `scripts/build_release.py`, macOS
  `build_macos.sh`, updated Windows `build.bat`
- Native macOS `.app` bundle support (Finder-launchable, bundled runtime)
- `runtime_paths.py` for frozen resource roots and OS log/data directories
- Real application icons (`logo.png`, `app.ico`, `app.icns`)
- GUI rotating file logging to the platform log directory when packaged
- Label content checkboxes in the GUI (Title, Author, ISBN, Barcode) so
  teachers can choose what appears on each printed label
- ``LabelContentOptions`` shared by settings, layout, and Excel placement
- `CompositeBookEnrichmentProvider`: sequential `BookEnrichmentProvider`
  pipeline (`FOUND`/`AMBIGUOUS` stop; `NOT_FOUND`/`ERROR` continue)
- `OpenLibraryEnrichmentProvider`: Open Library Search API fallback after
  Google Books `NOT_FOUND`
- `BookEnrichmentResult.provider_name` for catalog attribution (diagnostics /
  benchmarks; not shown in the teacher UI)

### Changed

- Google Books search strategy: most-specific-first queries
  (`intitle:… inauthor:surname` → surname form → free text); continue past
  confident metadata matches that lack a usable ISBN; DEBUG per-query
  diagnostics (no API keys). Confidence thresholds unchanged.
- Default enrichment wiring uses `CompositeBookEnrichmentProvider` with
  Google Books first and Open Library second.
- Print barcodes render at 600 DPI with taller bars and fill more of the
  label; barcode row allocation grows when fewer text fields are shown

### Fixed

- Packaged builds now collect `python-barcode` font data so EAN-13 PNG
  rendering no longer fails with ``cannot open resource`` / empty barcodes
- Zero-byte barcode leftovers are regenerated instead of skipped as existing
- Label layout now expands ``Book.copies`` into multiple physical labels
- Barcode images are constrained to the barcode cell and centered so they no
  longer cover title/author/ISBN on labels below

### Changed

- Packaged apps resolve assets via PyInstaller `_MEIPASS` instead of the
  development project tree
- Product description clarified for Excel inventory / Avery label workflow
- Added `APP_EXECUTABLE_NAME` and `APP_BUNDLE_IDENTIFIER` packaging metadata
- Renamed project directory from `barcode-generator` to `barcode_generator`
- Adopted standard src-layout package `classroom_library_label_maker`
- Reorganized assets into `icons/`, `templates/`, `sample-data/`, `resources/`
- Expanded domain models and `ApplicationSettings` / `ProjectPaths`
- Switched file logging to `RotatingFileHandler` (`logs/application.log`)
- Moved CLI parsing and command dispatch into `cli/` (`main.py` is startup only)
- Centralized product identity in `metadata.py` (CLI, logs, package exports)

### Added

- Extension packages `services/lookups/` and `services/covers/`
- `services/protocols.py` for future enrichment providers
- `tests/integration/` placeholder for end-to-end tests
- `exceptions.py` application error hierarchy
- CLI subcommands: `generate`, `version`, plus reserved `validate` / `clean` /
  `diagnostics`
- `metadata.py` as the single source of truth for application metadata

## [0.1.0] - 2026-07-24 — Initial Development

### Added

- Project created
- Project architecture established
- Barcode engine skeleton (`services`, `models`, `config`, `logger`, `utils`)
- Test framework (pytest) with starter coverage
- Logging framework
- Configuration framework
- Assets, runtime folders, and packaging scaffolding for future releases

[Unreleased]: https://github.com/bfank02/Classroom-Library-Label-Maker/compare/barcode-generator-v0.1.0...HEAD
[0.1.0]: https://github.com/bfank02/Classroom-Library-Label-Maker/releases/tag/barcode-generator-v0.1.0
