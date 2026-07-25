# Classroom Library Label Maker

## Sprint 1 – Barcode Engine

- [x] Project structure
- [x] ISBN validator
- [x] Barcode generation service
- [x] Batch processing service
- [x] Excel import
- [x] Label templates + label layout
- [x] Workbook generation (import → barcodes → layout → save)
- [x] CLI generate → WorkbookGenerationService
- [x] Workbook presentation / print readiness
- [x] Logging
- [ ] Package as EXE
- [ ] Remove deprecated `BatchProcessor` / `BarcodeGenerator` stubs

## Sprint 2 – Excel Integration

- [ ] Dashboard
- [ ] Books sheet
- [ ] Generate Barcodes button (wire to `WorkbookGenerationService`)
- [ ] Status updates

## Sprint 3 – Label Printing

- [ ] Print preview
- [ ] Print integration

Note: Avery 5160 geometry, label layout, and label workbook save are already
implemented (`label_templates/`, `LabelLayoutService`,
`WorkbookGenerationService`). Sprint 3 is printing only.
