from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import as_file, files
from pathlib import Path


_SCRIPT_PACKAGE = "modwire_extraction.extractors.scripts"


@contextmanager
def extractor_script_path(extractor_file: str) -> Iterator[Path]:
    resource = files(_SCRIPT_PACKAGE).joinpath(extractor_file)
    if not resource.is_file():
        raise FileNotFoundError(f"Extractor script {extractor_file} not found")
    with as_file(resource) as path:
        yield path.resolve()


def read_extractor_script(extractor_file: str) -> bytes:
    resource = files(_SCRIPT_PACKAGE).joinpath(extractor_file)
    if not resource.is_file():
        raise FileNotFoundError(f"Extractor script {extractor_file} not found")
    return resource.read_bytes()


__all__ = ["extractor_script_path", "read_extractor_script"]
