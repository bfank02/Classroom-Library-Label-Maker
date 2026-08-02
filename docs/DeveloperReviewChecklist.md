# Developer Review Checklist

Use this checklist for every **completed feature** before merge.

Copy into a PR description or a filled
[Feature Review](templates/FeatureReviewTemplate.md) as needed.

---

## Architecture

- [ ] Responsibilities remain separated (no feature owns another feature’s job)
- [ ] No duplicated business logic (reuse existing services/models)
- [ ] Public API reviewed against [PublicAPI.md](PublicAPI.md)
- [ ] Dependencies remain directional (e.g. services → rendering protocol;
      no third-party barcode types in orchestration)
- [ ] Extension points used instead of hardwiring future UI/Excel concerns
- [ ] Catalog / ISBN enrichment goes through `BookEnrichmentProvider` +
      `BookEnrichmentService` (no HTTP or provider types in
      `WorkbookGenerationService`; gate with `lookup_missing_isbns`)
- [ ] Interactive ISBN review uses `ReviewSession` + `BookReviewService`
      (GUI must not own review indexes or call Google Books during review;
      presentation lives in `ReviewWizardDialog`; Skip/selection auto-advance,
      visual polish, and manual ISBN entry UI are presentation/session actions
      and must not invent a parallel review state or change produce/inventory)
- [ ] Manual ISBN entry uses `IsbnValidator` + `ReviewSession.select_manual_isbn`
      (ordinary `ReviewDecision`; no provider-specific branching downstream)
- [ ] Successful generation ends on Ready to Print (`CompletionView`); Done
      returns Home without clearing Files settings; no new generation logic
- [ ] Home editable fields use session dirty tracking so `_refresh_ui` does
      not overwrite in-progress edits (Label File Name and future fields);
      drafts commit at editingFinished / Generate; preference semantics
      unchanged
- [ ] Home layout remains stable under resize (minimum size, form policies,
      no overlapping Files/Options/Actions sections)
- [ ] Home header and Ready to Print share `gui/theme.py` colors/typography
      (presentation only; no workflow changes); headings remain higher
      contrast than secondary text and filenames
- [ ] Reviewed ISBNs must flow through one authoritative book list into
      barcode generation, label layout, and inventory update
      (`prepare` → review → `produce`; no parallel collections). Filter
      intentionally skipped / missing-ISBN books immediately before produce
      only; inventory keeps the full authoritative collection
- [ ] Don't Generate Label / manual ISBN / catalog selection are ordinary
      `ReviewSession` decisions; produce must not understand skip semantics
      beyond receiving the filtered eligible list
- [ ] Label titles use `fit_label_title` (font metrics); geometry prefers
      enough title-band height before shrink/ellipsis; max two lines; no
      overlap with author or barcode
- [ ] New work uses `WorkbookGenerationService` (or its collaborators),
      not deprecated `BatchProcessor` / `BarcodeGenerator`
- [ ] Unexpected failures map to the existing exception hierarchy where
      applicable
- [ ] Template selection uses `label_template_id` (not deprecated
      `default_label_type`)
- [ ] Excel output goes through `WorkbookWriter` (services must not import
      openpyxl)
## Testing

- [ ] Unit tests added for new behavior
- [ ] Existing tests pass (`python -m pytest` from `barcode_generator/`)
- [ ] Coverage maintained for the touched feature area
- [ ] End-to-end / manual verification completed where applicable
      (e.g. real PNG generation, barcode scan, batch mixed outcomes)
- [ ] Flaky or brittle checks avoided (prefer contracts over pixel-perfect
      asserts unless intentionally golden-tested)

## Public API

- [ ] List **new** public classes
- [ ] List **new** public methods
- [ ] List **new** models / enums
- [ ] List **new** interfaces / protocols
- [ ] Stability labels assigned (Stable / Experimental / Internal) in
      [PublicAPI.md](PublicAPI.md)
- [ ] Backward compatibility documented (no breaks, or major-version justified)
- [ ] Private helpers remain private (leading underscore / not exported)

## Documentation

- [ ] README updated if needed (`barcode_generator/README.md` and/or root)
- [ ] Architecture updated if needed ([Architecture.md](Architecture.md))
- [ ] Public API updated ([PublicAPI.md](PublicAPI.md))
- [ ] Feature Decision Record created under `docs/decisions/` when the feature
      is accepted
- [ ] Developer-facing how-tos updated when workflow changes
      (e.g. scan verification, golden images)

## Release

- [ ] Build succeeds (`.\build.bat` when packaging is in scope)
- [ ] Executable verified (if applicable)
- [ ] Version / tag ready (`VERSION`, `metadata.APP_VERSION`, `CHANGELOG.md`)
- [ ] No secrets or generated runtime artifacts committed

---

## Quick commands

```powershell
cd barcode_generator
python -m pytest
python -m ruff check src tests
python -m classroom_library_label_maker --version
# Optional packaging
.\build.bat
```
