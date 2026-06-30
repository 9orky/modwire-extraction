from __future__ import annotations

from pathlib import Path

from ..base import BatchConfig, ExtractorRuntime, SourceExtractor


class TypeScriptExtractor(SourceExtractor):
    @property
    def runtime(self) -> ExtractorRuntime:
        return ExtractorRuntime(
            language="typescript",
            file_extensions=(".ts", ".tsx", ".js", ".jsx"),
            command=("node",),
            script_path=Path(__file__).with_name("script.js"),
        )

    @property
    def batch_config(self) -> BatchConfig:
        return BatchConfig(
            size=500,
            parallel_threshold=1000,
            parallel_size=500,
            max_workers=16,
            output_format="jsonl",
        )
