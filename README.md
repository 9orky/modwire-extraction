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

Before publishing manually, choose the release version in `pyproject.toml`,
remove stale local artifacts, build a fresh distribution, and upload only the
expected version files:

```bash
rm -rf build dist src/*.egg-info
python -m build
twine check dist/*
twine upload dist/modwire_extraction-1.0.0*
```

The preferred release path is GitHub Actions. Publish a GitHub Release tagged
`vX.Y.Z` or `X.Y.Z` after configuring PyPI Trusted Publishing for workflow
`workflow.yml` and GitHub Environment `pypi`. The release workflow sets the
package version from the release tag before building.
