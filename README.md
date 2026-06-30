# modwire-extraction

Extraction implementation for Modwire.

The package builds code maps for supported source trees and exposes the public
API from `modwire_extraction.extraction`.

## Install

```bash
pip install modwire-extraction
```

## Development

```bash
python -m pip install -e ".[dev]"
pytest
python -m build
twine check dist/*
```

Before publishing, choose the release version in `pyproject.toml`, build a
fresh distribution, and upload it with:

```bash
twine upload dist/*
```
