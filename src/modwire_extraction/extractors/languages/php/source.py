from __future__ import annotations

from pathlib import Path

from ..base import BatchConfig, ExtractorRuntime, SourceExtractor


class PhpExtractor(SourceExtractor):
    @property
    def runtime(self) -> ExtractorRuntime:
        return ExtractorRuntime(
            language="php",
            file_extensions=(".php",),
            command=("php",),
            script_path=Path(__file__).with_name("script.php"),
        )

    @property
    def batch_config(self) -> BatchConfig:
        return BatchConfig(
            size=500,
            parallel_threshold=500,
            parallel_size=500,
            max_workers=16,
            output_format="jsonl",
        )
