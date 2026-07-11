# Changelog

## 2.0.0 - Unreleased

### Added

- Add distinct typed `FileId`, `ModuleId`, and `ImportSpecifier` concepts.
- Preserve original and normalized import specifiers with explicit resolved,
  external, or unresolved state.
- Resolve unique project-local imports to extension-bearing tracked file IDs.
- Raise structured duplicate-identity errors instead of overwriting files or
  logical modules.

### Changed

- Keep file extensions in source IDs and callable source identities.
- Restrict dependency graph nodes to the tracked file-ID namespace.
- Store import specifier and resolution state on every dependency edge.
- Add a version 2 migration guide for serialized maps and query consumers.

## 1.0.3 - 2026-07-11

### Fixed

- Restore the `QueryableCodeMap.cm` compatibility alias.
- Mark `load_extractor` as an intentional public re-export.

### Changed

- Derive distribution versions from strict SemVer SCM tags.
- Adopt the Modwire reusable CI and GitHub-Release-driven publication contract.

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
