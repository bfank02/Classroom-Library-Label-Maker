# Software Design Specification

## Overview

Classroom Library Label Maker generates printable barcode labels for classroom library books from Excel workbook data.

## Components

- **Excel workbook (`excel/`)** — teacher-facing inventory and label workflow (`.xlsm` + VBA)
- **Barcode generator (`barcode_generator/`)** — Python package `classroom_library_label_maker` that validates ISBNs and produces barcode images
- **Installer (`installer/`)** — packaging and setup for end users
- **Samples (`samples/`)** — example workbooks for demos and testing

## Data flow

1. Teacher maintains book inventory in Excel.
2. VBA/export hands off JSON data to the barcode generator EXE / CLI.
3. Generator validates ISBNs, writes PNG barcodes under `output/barcodes/`, and returns a results JSON file.
4. Excel (and later label printing) consumes results for status updates and Avery layouts.

## Domain contract (barcode engine)

Primary models: `Book`, `ValidationResult`, `BarcodeGenerationResult`, `ApplicationSettings`.

See [`Architecture.md`](Architecture.md) for package layout, extension points, and coding standards.
