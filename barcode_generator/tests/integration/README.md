# Integration tests

End-to-end tests that exercise the **production library workflow** with real
adapters (openpyxl, python-barcode), not in-memory fakes.

## Purpose

Unit tests isolate services with stubs (`InMemoryWorkbookWriter`, fake
importers). Integration tests verify that those pieces work together when
wired the way production code is wired:

1. `ExcelImportService` (real `OpenPyxlWorkbookReader`)
2. `BatchProcessingService` / `BarcodeGenerationService` (real renderer)
3. `LabelLayoutService`
4. `OpenPyxlWorkbookWriter` → saved `.xlsx`
5. Re-open the output workbook with openpyxl

## Canonical dataset

[`tests/assets/workbooks/integration_inventory.xlsx`](../assets/workbooks/integration_inventory.xlsx)

- Sheet: `Books`
- Columns: `ISBN`, `Title`, `Author`, `Copies`
- **31** valid ISBN-13 rows (forces Avery 5160 pagination onto 2 pages)
- Includes well-known classics plus synthetic valid ISBNs

Regenerate (if needed):

```powershell
cd barcode_generator
python tests\assets\workbooks\_generate_integration_inventory.py
```

## How to run

From `barcode_generator/`:

```powershell
# Integration package only
python -m pytest tests\integration -v

# Single E2E test
python -m pytest tests\integration\test_workbook_generation_e2e.py -v

# Full suite (includes integration)
python -m pytest
```

All outputs are written under pytest’s temporary directory — no user files or
persistent artifacts.

## Why real adapters?

In-memory writers prove orchestration logic. They cannot prove that:

- openpyxl workbooks save and reopen
- barcode PNGs embed into worksheets
- page worksheets (`Labels 1`, `Labels 2`) are created correctly

This package exists so release readiness includes that proof.
