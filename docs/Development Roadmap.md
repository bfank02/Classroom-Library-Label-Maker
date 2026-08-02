# Development Roadmap

## Coding standards (ongoing)

- Python 3.13+, PEP 8 / PEP 257, type hints, dataclasses, `pathlib`
- Package: `classroom_library_label_maker` under `barcode_generator/src/`
- Thin `main.py`; business logic in `services/`
- Logging configured only at startup (`RotatingFileHandler` + console)
- VERSION + CHANGELOG for releases

## Phase 1 — Foundation / Barcode Engine

- [x] Project scaffolding and documentation
- [x] Proper src-layout Python package
- [x] Domain models (`Book`, `ValidationResult`, `BarcodeGenerationResult`, …)
- [x] Configuration (`ApplicationSettings`, `ProjectPaths`, VERSION)
- [x] Production logging skeleton
- [x] Test framework + fixtures / integration placeholder
- [x] ISBN-13 check-digit validation
- [x] Rendering package scaffold (`BarcodeRenderer` / `PythonBarcodeRenderer`)
- [x] EAN-13 PNG generation (`BarcodeGenerationService` + python-barcode / Pillow)
- [x] Batch processing engine (`BatchProcessingService` over Book collections)
- [x] Excel import engine (`ExcelImportService` + `OpenPyxlWorkbookReader`)
- [x] Label layout engine (`LabelLayoutService` + `LabelSheetTarget`)
- [x] Workbook generation service (`WorkbookGenerationService` + `WorkbookWriter`)
- [x] CLI `generate` → `WorkbookGenerationService`
- [x] Workbook presentation / print readiness (openpyxl adapters)
- [x] Cross-platform desktop GUI (PySide6) over `WorkbookGenerationService`
- [x] Background generation + stage progress in the status line
- [x] Desktop product polish (RC3.5 UX / accessibility pass)
- [ ] Remove deprecated stubs (`BatchProcessor` / `BarcodeGenerator`) when unused
- [ ] Package as EXE (`build.bat` / PyInstaller)

## Phase 2 — Excel Integration

- [ ] Excel workbook skeleton and VBA module layout
- [ ] Dashboard sheet
- [ ] Books sheet (aligned with `Book` fields)
- [ ] Generate Barcodes button → invoke EXE / JSON contract
  (wire to `WorkbookGenerationService`)
- [ ] Status updates from results JSON

## Phase 3 — Label Printing

- [ ] Print preview
- [ ] Print integration

Label **geometry**, **layout**, and workbook **save** already exist.
Phase 3 is printing only.
## Phase 4 — Packaging & distribution

- [ ] Installer / setup under `installer/`
- [x] Sample books workbook under `samples/`
- [ ] First public release under `releases/`

## Phase 5 — Extensibility

- [x] Book enrichment architecture (`BookEnrichmentService`,
      `BookEnrichmentProvider`, `NullBookEnrichmentProvider`)
- [x] Google Books enrichment provider (`GoogleBooksEnrichmentProvider`)
- [x] In-memory enrichment cache on `BookEnrichmentService` (title/author key)
- [x] Wire enrichment into generation (`lookup_missing_isbns`, GUI checkbox,
      progress stage, `EnrichmentSummary`)
- [x] Enrichment review details (`ReviewItem` + ISBN Lookup Summary in GUI/CLI)
- [x] Candidate preservation for interactive review (`ReviewCandidate` on
      `BookEnrichmentResult` / `ReviewItem`; ambiguous peers retained; no
      review dialog yet)
- [x] User-facing confidence labels (`confidence_score` +
      `confidence_label` / `confidence_label_for_score`; no GUI yet)
- [x] Interactive review service (`ReviewSession`, `ReviewDecision`,
      `ReviewSessionResult`, `BookReviewService`) — no GUI yet
- [x] Interactive review wizard (`ReviewWizardDialog` over `ReviewSession`)
- [x] Persist selected / auto-enriched ISBNs to an updated inventory workbook
      copy after review (`InventoryUpdateService`; original never overwritten)
- [x] Google Books API key integration (config-only env read, startup
      validation, authenticated pacing, anonymous fallback on 401/403)
- [x] Improved Google Books search strategy (most-specific-first queries;
      continue past metadata matches without ISBN; DEBUG diagnostics)
- [x] Composite enrichment provider pipeline
      (`CompositeBookEnrichmentProvider`; Google Books only for now)
- [x] Open Library enrichment provider (secondary catalog after Google
      `NOT_FOUND`; provider attribution on `BookEnrichmentResult`)
- [ ] Additional catalog providers
- [ ] Cover image downloads (`services/covers/`)
- [ ] Inventory / checkout / reading-level workflows
- [ ] Additional barcode symbologies and label types
- [ ] Automatic updates

## Version 1.4 — Desktop UX

- [x] Files section refinement (Label Folder + editable Label File Name;
      independent persistence; stem selection on focus)
- [x] Review wizard workflow refinement (Skip / selection auto-advance;
      Finish Review on final item; no Next button)
- [x] Ready to Print completion experience (full-page summary; Done → Home)
- [x] Review experience polish (section hierarchy, cards, badges, skipped
      presentation; presentation-only)
- [x] Home screen organization & polish (Files / Options / Actions; header;
      version footer)

## Version 1.4.1 — Correctness

- [x] Reviewed ISBNs drive barcodes/labels/inventory via prepare → review →
      produce (single authoritative book collection)
- [x] Manual ISBN entry in Review Wizard (ordinary `ReviewDecision`; ISBN-10/13
      via `IsbnValidator`; no produce/inventory branching)
- [x] Intentional label skipping: Don't Generate Label; filter skipped books
      before produce; inventory retains rows; Ready to Print summary counts

## Version 1.4.2 — Home stability & label titles

- [x] Home dirty-field tracking so Label File Name and future edits survive
      Options/UI refreshes; commit at Generate / editingFinished
- [x] Home layout stability (minimum size, form row policy, no section overlap)
- [x] Adaptive label title rendering: taller title band (3 rows with barcode),
      font-metrics fit helper (`fit_label_title`), shrink then ellipsis,
      Excel + PDF; max two lines without clipping/overlap
- [x] Visual accessibility polish: shared `gui/theme.py` tokens; Home header
      and Ready to Print contrast/typography hierarchy (presentation only)

See also: [`Architecture.md`](Architecture.md), [`../TASKS.md`](../TASKS.md).
