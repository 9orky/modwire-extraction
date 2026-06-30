from __future__ import annotations


from ..base import SourceExtractor


class TypeScriptExtractor(SourceExtractor):
    language = "typescript"
    file_extensions = (".ts", ".tsx", ".js", ".jsx")
    command = "node"
    batch_size = 500
    batch_output_format = "jsonl"
    batch_parallel_threshold = 1000
    batch_parallel_size = 500
    max_batch_parallel_workers = 16
