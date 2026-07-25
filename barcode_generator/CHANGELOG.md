# Changelog

All notable changes to Classroom Library Label Maker are documented in this
file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.1] - 2026-07-25 — Packaging hotfix

### Fixed

- Packaged Windows EXE now bundles the `python-barcode` font so barcode PNGs
  generate correctly (previously every label became `[barcode placeholder]`)

## [1.0.0] - 2026-07-25 — Public beta release candidate

### Added

- Windowed Windows GUI release ZIP (`releases/`) with product-named EXE
- Production rotating logs under the per-user application data folder
- Application branding icons (`assets/icons/app.ico`, `logo.png`)
- Teacher Quick Start, sample inventory workbook, and first-run dialog defaults
- Visible success-with-warnings completion state for review-before-print

### Changed

- Version synchronized to **1.0.0**
- Product description updated for Excel inventory → Avery label workflow
- Distribution name aligned to `classroom-library-label-maker`
- GUI failure messages point to the configured log file path

## [0.1.0] - 2026-07-24 — Initial Development

### Added

- Project created
- Project architecture established
- Barcode engine skeleton (`services`, `models`, `config`, `logger`, `utils`)
- Test framework (pytest) with starter coverage
- Logging framework
- Configuration framework
- Assets, runtime folders, and packaging scaffolding for future releases

[Unreleased]: https://github.com/bfank02/Classroom-Library-Label-Maker/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/bfank02/Classroom-Library-Label-Maker/releases/tag/v1.0.1
[1.0.0]: https://github.com/bfank02/Classroom-Library-Label-Maker/releases/tag/v1.0.0
[0.1.0]: https://github.com/bfank02/Classroom-Library-Label-Maker/releases/tag/barcode-generator-v0.1.0
