# Classroom Library Label Maker

## Sprint 1 – Barcode Engine

- [x] Project structure
- [x] ISBN validator
- [x] Barcode generation service
- [x] Batch processing service
- [x] Excel import
- [x] Label templates + label layout
- [x] Logging
- [ ] Package as EXE
- [ ] Migrate CLI off deprecated `BatchProcessor` / `BarcodeGenerator`

## Sprint 2 – Excel Integration

- [ ] Dashboard
- [ ] Books sheet
- [ ] Generate Barcodes button (canonical: Import → Batch → Layout)
- [ ] Status updates

## Sprint 3 – Label Printing

- [ ] Workbook save after layout
- [ ] Print preview
- [ ] Print integration

Note: Avery 5160 geometry and label layout are already implemented in the
Python package (`label_templates/` + `LabelLayoutService`). Sprint 3 is
save/print only.
