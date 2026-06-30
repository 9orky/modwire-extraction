# modwire-extraction

Extraction implementation for Modwire.

The package is split into three public packages:

- `modwire_extraction.extractors` returns source-file extraction results.
- `modwire_extraction.graph` builds dependency graphs from extracted source files.
- `modwire_extraction.code_map` composes extraction and graph data into a `CodeMap`.

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
