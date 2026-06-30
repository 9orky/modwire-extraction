# Changelog

## 1.0.0 - 2026-06-30

Initial stable release of `modwire-extraction`.

### Added

- Public `ModwireExtraction` API for generating queryable source maps from
  project trees.
- Public code map, query result, dependency graph, and extractor-loading
  helpers.
- Python extractor support using the active Python interpreter.
- TypeScript, TSX, JavaScript, and JSX extractor support through the bundled
  TypeScript runtime.
- PHP extractor support through the bundled PHP runtime.
- Python 3.11, 3.12, and 3.13 package support.
- GitHub Actions release workflow for building distributions and publishing to
  PyPI through Trusted Publishing.

### Notes

- Dependency graph edges use normalized import strings. Imports such as
  `domain/model/user` are not represented as the source ID
  `src/domain/model/user`.
- Serialized `CodeMap` JSON is intended for same-version interchange in 1.0.0.
  Do not treat the JSON shape as a cross-version compatibility contract yet.
- TypeScript and PHP helper build files are included as package data because
  they are part of the bundled extractor runtimes and reproducible maintenance
  path.
