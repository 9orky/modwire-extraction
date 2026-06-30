from __future__ import annotations

import os
import sys
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context

from dataclasses import dataclass
from posixpath import normpath
from pathlib import Path, PurePosixPath

from ...source import SourceExport, SourceFile, SourceImport
from ...base import (
    SourceExtraction,
    SourceExtractor,
)


@dataclass(frozen=True)
class PythonSourceIndex:
    known_source_ids: set[str]
    unique_suffixes: dict[str, str | None]

    @classmethod
    def build(cls, known_source_ids: set[str]) -> PythonSourceIndex:
        suffixes: dict[str, str | None] = {}
        for source_id in known_source_ids:
            parts = source_id.split("/")
            for index in range(len(parts)):
                suffix = "/".join(parts[index:])
                previous = suffixes.get(suffix)
                if previous is None and suffix in suffixes:
                    continue
                if previous is not None and previous != source_id:
                    suffixes[suffix] = None
                    continue
                suffixes[suffix] = source_id
        return cls(known_source_ids=known_source_ids, unique_suffixes=suffixes)
