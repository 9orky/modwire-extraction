from __future__ import annotations


from ..base import (
    SourceExtractor,
)


class PhpExtractor(SourceExtractor):
    language = "php"
    file_extensions = (".php",)
    command = "php"
    batch_size = 500
    batch_output_format = "jsonl"
    batch_parallel_threshold = 500
    batch_parallel_size = 500
    max_batch_parallel_workers = 16
