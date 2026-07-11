# modwire-extraction

Extraction implementation for Modwire.

The primary API starts from `ModwireExtraction`:

```python
from pathlib import Path

from modwire_extraction import ModwireExtraction, QueryableCodeMap

queryable_map: QueryableCodeMap = ModwireExtraction(Path("src")).generate_queryable_map("python")
print(queryable_map.source_ids())
```

Public data and query helpers are exported from:

- `modwire_extraction` for `ModwireExtraction` and `QueryableCodeMap`.
- `modwire_extraction.code` for `CodeMap` and query result types.
- `modwire_extraction.dependency` for dependency graph helpers.
- `modwire_extraction.extractors` for extractor loading.

## Compatibility notes

Version 2 uses extension-bearing physical file IDs, separate logical module
IDs, and dependency edges resolved to tracked files. Original and normalized
import specifiers remain available with an explicit resolution state.

See [Migrating to modwire-extraction 2](https://github.com/modwire/modwire-extraction/blob/main/docs/migration-2.md)
for the complete breaking-contract guide.

Serialized `CodeMap` JSON remains a same-major interchange contract. Regenerate
1.x maps before loading them with version 2.

TypeScript and PHP helper build files are included as package data because
they are part of the bundled extractor runtimes and reproducible maintenance
path.

## Install

```bash
pip install modwire-extraction
```

Python extraction works with the active Python interpreter. TypeScript,
JavaScript, TSX, and JSX extraction require `node` on `PATH`. PHP extraction
requires `php` on `PATH`.

## Development

```bash
python -m pip install -e ".[dev]"
pytest
python -m build
twine check dist/*
```

For local verification, build a fresh distribution from the current Git state:

```bash
python -m build
twine check dist/*
```

Releases use strict SemVer tags. Create and push the tag first, then publish its
GitHub Release. That release invokes the shared build and asset workflows before
trusted publishing sends the same distributions to PyPI.

```sh
git tag -a v2.0.0 -m "v2.0.0"
git push origin v2.0.0
gh release create v2.0.0 --verify-tag --generate-notes --title v2.0.0
```
