import abc

from pathlib import Path

from pydantic import BaseModel

from ..source import SourceFile


class SourceExtraction:
    files: dict[str, SourceFile]
    files_found: int
    files_excluded: int


class BatchConfig:
    size: int = 0
    parallel_threshold: int = 0
    parallel_size: int = 0
    max_workers: int = 1
    output_format: str = "json"


class ExtractorRuntime():
    language: str
    file_extensions: tuple[str, ...]
    command: str


class SourceExtractor(abc.ABC):
    @property
    @abc.abstractmethod
    def runtime(self) -> ExtractorRuntime:
        raise NotImplementedError
    
    @property
    @abc.abstractmethod
    def batch_config(self) -> BatchConfig:
        raise NotImplementedError

    def extract_source(self, root: Path) -> SourceExtraction:
        pass
