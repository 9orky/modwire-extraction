# Migrating to modwire-extraction 2

Version 2 separates physical files, logical modules, and import specifiers. This
is a breaking serialized-contract change required for resolved dependency
graphs.

## File and module identities

`SourceExtraction.files` is now keyed by repository-relative `FileId` values
that retain the file extension. For example:

```text
1.x: src/domain/model/user
2.x: src/domain/model/user.py
```

Each `SourceFile` also carries its `file_id` and logical `module_id`.
`SourceExtraction.modules` maps every unique `ModuleId` to its `FileId`.
Identity types are imported from their defining module:

```python
from modwire_extraction.identity import FileId, ImportSpecifier, ModuleId
```

Do not remove extensions from file IDs or use import strings as file IDs.
Repositories containing ambiguous logical module identities receive a
structured `DuplicateIdentityError` instead of silently losing a file.

## Import resolution

`SourceImport.path` still contains the original import specifier and
`normalized_path` still contains the extractor-normalized specifier. Both are
typed as `ImportSpecifier`. Two fields are added:

- `resolution`: `resolved`, `external`, or `unresolved`;
- `target_file_id`: the tracked `FileId` for a uniquely resolved local import,
  otherwise `None`.

Resolution is language-neutral. The shared resolver consumes normalized
specifier, module, and export data; it contains no language, framework,
namespace-prefix, source-root, or extension-priority rules.

## Dependency graphs

Graph nodes now use one namespace and contain tracked `FileId` values only.
Every edge retains its `specifier` and `resolution`. A resolved edge has a
tracked `to_id`; external and unresolved edges have `to_id=None` and remain
queryable through their explicit state.

For `QueryableCodeMap` consumers:

- pass extension-bearing `FileId` values to file and dependency queries;
- use `tracked_dependency_edges()` for resolved local edges;
- use `dependency_edges()` and filter `edge.resolution` when external and
  unresolved edges must be distinguished;
- stop looking for external import strings in `dependency_nodes()`.

Serialized `CodeMap` payloads from 1.x must be regenerated. They cannot be
loaded as version 2 maps because file identity and graph edge shapes changed.
