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
      presentation lives in `ReviewWizardDialog`; Skip/selection auto-advance
      is UI-only and must not change domain review logic)
- [ ] Successful generation ends on Ready to Print (`CompletionView`); Done
      returns Home without clearing Files settings; no new generation logic
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
