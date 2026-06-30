from __future__ import annotations

import sys

from ..base import BatchConfig, ExtractorRuntime, SourceExtractor


class PythonExtractor(SourceExtractor):
    language = "python"
    file_extensions = (".py",)
    command = sys.executable

    @property
    def runtime(self) -> ExtractorRuntime:
        return ExtractorRuntime(
            lan
        )

    @property
    def batch_config(self) -> BatchConfig:
        raise NotImplementedError


