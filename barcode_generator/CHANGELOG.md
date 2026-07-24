# Changelog

All notable changes to the Classroom Library barcode generator are documented
in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

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
