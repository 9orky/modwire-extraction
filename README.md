# modwire-extraction

Extraction implementation for Modwire.

The primary API starts from `ModwireExtraction`:

```python
from pathlib import Path

from modwire_extraction import ModwireExtraction

queryable_map = ModwireExtraction(Path("src")).generate_queryable_map("python")
print(queryable_map.source_ids())
```

Public data and query helpers are exported from:

- `modwire_extraction` for `ModwireExtraction`.
- `modwire_extraction.code` for `CodeMap`, `QueryableCodeMap`, and query result types.
- `modwire_extraction.dependency` for dependency graph helpers.
- `modwire_extraction.extractors` for extractor loading.

## Compatibility notes

The public Python import paths listed above are the supported API surface for
1.0.0.

Dependency graph edges use normalized import strings. Imports such as
`domain/model/user` are not represented as the source ID
`src/domain/model/user`.

Serialized `CodeMap` JSON is intended for same-version interchange in 1.0.0.
Do not treat the JSON shape as a cross-version compatibility contract yet.

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
git tag -a v1.0.3 -m "v1.0.3"
git push origin v1.0.3
gh release create v1.0.3 --verify-tag --generate-notes --title v1.0.3
```
