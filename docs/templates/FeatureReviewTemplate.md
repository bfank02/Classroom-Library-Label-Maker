# Feature Review

> Copy this template for each completed feature review.
> Fill every section. Link related FDRs and PRs.

**Feature:**  
**Reviewer:**  
**Date:**  
**Status:** Draft | Approved | Changes requested  
**Related FDR:**  
**Related PR:**  

---

## Summary

Brief description of what shipped and why.

## Files Modified

- …

## New Public API

| Symbol | Module | Stability | Notes |
|--------|--------|-----------|-------|
| | | Stable / Experimental / Internal | |

## Changed Public API

| Symbol | Change | Backward compatible? |
|--------|--------|----------------------|
| | | Yes / No (explain) |

## Backward Compatibility

- [ ] No breaking changes to Stable APIs
- [ ] Any break is intentional and versioned

Notes:

## Tests

- Unit tests added/updated:
- Suite result (`pytest`):
- Manual / E2E verification:

## Documentation

- [ ] [PublicAPI.md](../PublicAPI.md) updated
- [ ] [Architecture.md](../Architecture.md) updated (if needed)
- [ ] README updated (if needed)
- [ ] FDR created/updated under `docs/decisions/`
- [ ] [DeveloperReviewChecklist.md](../DeveloperReviewChecklist.md) completed

## Known Limitations

- …

## Future Enhancements

- …

## Checklist sign-off

Confirm items in [DeveloperReviewChecklist.md](../DeveloperReviewChecklist.md):

- [ ] Architecture
- [ ] Testing
- [ ] Public API
- [ ] Documentation
- [ ] Release
