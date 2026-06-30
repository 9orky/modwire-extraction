from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from ..source import SourceFile


class SourceExtraction(BaseModel):
    files: dict[str, SourceFile]
    files_found: int
    files_excluded: int


class BatchConfig(BaseModel):
    size: int = 0
    parallel_threshold: int = 0
    parallel_size: int = 0
    max_workers: int = 1
    output_format: str = "json"


class SourceExtractor(Protocol):
    language: str
    file_extensions: tuple[str, ...]
    command: str
    batch_config: BatchConfig
