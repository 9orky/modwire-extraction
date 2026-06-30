from __future__ import annotations

import sys
from pathlib import Path

from ..base import BatchConfig, ExtractorRuntime, SourceExtractor


class PythonExtractor(SourceExtractor):
    @property
    def runtime(self) -> ExtractorRuntime:
        return ExtractorRuntime(
            language="python",
            file_extensions=(".py",),
            command=(sys.executable,),
            script_path=Path(__file__).with_name("script.py"),
        )

    @property
    def batch_config(self) -> BatchConfig:
        return BatchConfig(size=500, output_format="json")
