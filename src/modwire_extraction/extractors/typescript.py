from __future__ import annotations

from dataclasses import dataclass
from posixpath import normpath
from pathlib import Path

from ..definitions import SourceExport, SourceImport
from .base import SourceExtraction, SourceExtractor, _extract_files


@dataclass(frozen=True)
class TypeScriptExtractor(SourceExtractor):
    language = "typescript"
    file_extensions = (".ts", ".tsx", ".js", ".jsx")
    command = "node"
    extractor_file = "typescript_extractor.js"
    batch_size = 500
    batch_output_format = "jsonl"
    batch_parallel_threshold = 1000
    batch_parallel_size = 500
    max_batch_parallel_workers = 16

    def extract_files(
        self,
        sources_root: Path,
        exclusions: tuple[str, ...],
        source_id_prefix: str = "",
    ) -> SourceExtraction:
        return _extract_files(
            self,
            sources_root,
            exclusions,
            source_id_prefix=source_id_prefix,
            batch_size=self.batch_size,
        )

    def normalize_import(
        self,
        source_id: str,
        source_import: SourceImport,
        known_source_ids: set[str],
    ) -> SourceImport:
        normalized_path = source_import.normalized_path
        if source_import.is_relative:
            parent = source_id.rpartition("/")[0]
            normalized_path = normpath(
                f"{parent}/{source_import.path}" if parent else source_import.path
            )
            normalized_path = self.normalize_source_id(normalized_path)

        return SourceImport.model_construct(
            path=source_import.path,
            is_relative=source_import.is_relative,
            normalized_path=normalized_path,
            imported_name=source_import.imported_name,
            is_aliased=source_import.is_aliased,
            crossing_type=source_import.crossing_type,
            file_barrier_crossed=(
                source_import.file_barrier_crossed
                and normalized_path in known_source_ids
            ),
            statement_id=source_import.statement_id,
            join_key=normalized_path if source_import.join_key else "",
            uses_joined_import=source_import.uses_joined_import,
            imported_symbols=source_import.imported_symbols,
        )

    def normalize_export(
        self,
        source_id: str,
        source_export: SourceExport,
        known_source_ids: set[str],
    ) -> SourceExport:
        normalized_path = source_export.normalized_path
        if source_export.is_relative:
            parent = source_id.rpartition("/")[0]
            normalized_path = normpath(
                f"{parent}/{source_export.path}" if parent else source_export.path
            )
            normalized_path = self.normalize_source_id(normalized_path)

        return SourceExport.model_construct(
            name=source_export.name,
            local_name=source_export.local_name,
            kind=source_export.kind,
            crossing_type=source_export.crossing_type,
            path=source_export.path,
            is_relative=source_export.is_relative,
            normalized_path=normalized_path,
            is_reexport=source_export.is_reexport,
            is_default=source_export.is_default,
            is_aliased=source_export.is_aliased,
            statement_id=source_export.statement_id,
        )


__all__ = ["TypeScriptExtractor"]
