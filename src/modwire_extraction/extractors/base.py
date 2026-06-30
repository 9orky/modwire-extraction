from __future__ import annotations

from pydantic import BaseModel
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from .source import SourceExport, SourceFile, SourceImport


class SourceExtraction(BaseModel):
    files: dict[str, SourceFile]
    files_found: int
    files_excluded: int


@dataclass(frozen=True)
class SourceExtractor:
    language: ClassVar[str]
    file_extensions: ClassVar[tuple[str, ...]]
    command: ClassVar[str]
    extractor_file: ClassVar[str]
    batch_size: ClassVar[int] = 0
    batch_output_format: ClassVar[str] = "json"
    batch_parallel_threshold: ClassVar[int] = 0
    batch_parallel_size: ClassVar[int] = 0
    max_batch_parallel_workers: ClassVar[int] = 1

    def extract_files(
        self,
        sources_root: Path,
        exclusions: tuple[str, ...],
        source_id_prefix: str = "",
    ) -> SourceExtraction:
        from ._process import ExtractorProcess

        return ExtractorProcess(self).extract_files(
            sources_root,
            exclusions,
            source_id_prefix=source_id_prefix,
        )

    def normalize_source_id(self, value: str) -> str:
        source_id = value.strip().strip("/")
        for file_extension in self.file_extensions:
            if source_id.endswith(file_extension):
                return source_id[: -len(file_extension)]
        return source_id

    def normalize_import(
        self,
        source_id: str,
        source_import: SourceImport,
        known_source_ids: set[str],
    ) -> SourceImport:
        if source_import.normalized_path in known_source_ids:
            return source_import
        return SourceImport.model_construct(
            path=source_import.path,
            is_relative=source_import.is_relative,
            normalized_path=source_import.normalized_path.strip().strip("/"),
            imported_name=source_import.imported_name,
            is_aliased=source_import.is_aliased,
            crossing_type=source_import.crossing_type,
            file_barrier_crossed=False,
            statement_id=source_import.statement_id,
            join_key=source_import.join_key,
            uses_joined_import=source_import.uses_joined_import,
            imported_symbols=source_import.imported_symbols,
        )

    def normalize_export(
        self,
        source_id: str,
        source_export: SourceExport,
        known_source_ids: set[str],
    ) -> SourceExport:
        return SourceExport.model_construct(
            name=source_export.name,
            local_name=source_export.local_name,
            kind=source_export.kind,
            crossing_type=source_export.crossing_type,
            path=source_export.path,
            is_relative=source_export.is_relative,
            normalized_path=source_export.normalized_path.strip().strip("/"),
            is_reexport=source_export.is_reexport,
            is_default=source_export.is_default,
            is_aliased=source_export.is_aliased,
            statement_id=source_export.statement_id,
        )

    def normalize_source_files(
        self,
        files: dict[str, SourceFile],
    ) -> dict[str, SourceFile]:
        known_source_ids = set(files)
        return {
            source_id: self.normalize_source_file(
                source_id,
                source_file,
                known_source_ids,
            )
            for source_id, source_file in files.items()
        }

    def normalize_source_file(
        self,
        source_id: str,
        source_file: SourceFile,
        known_source_ids: set[str],
    ) -> SourceFile:
        exports = [
            self.normalize_export(source_id, source_export, known_source_ids)
            for source_export in source_file.exports
        ]
        exports = self._with_module_export(source_id, exports)

        return SourceFile.model_construct(
            imports=[
                self.normalize_import(source_id, source_import, known_source_ids)
                for source_import in source_file.imports
            ],
            exports=exports,
            classes=source_file.classes,
            interfaces=source_file.interfaces,
            types=source_file.types,
            abstract_classes=source_file.abstract_classes,
            functions=source_file.functions,
            values=source_file.values,
            callables=source_file.callables,
            calls=source_file.calls,
            line_count=source_file.line_count,
            code_line_count=source_file.code_line_count,
            public_symbol_count=source_file.public_symbol_count,
        )

    def _with_module_export(
        self,
        source_id: str,
        exports: list[SourceExport],
    ) -> list[SourceExport]:
        module_export = SourceExport.model_construct(
            name=source_id,
            local_name=source_id,
            kind="module",
            crossing_type="module",
            path=source_id,
            is_relative=False,
            normalized_path=source_id,
            is_reexport=False,
            is_default=False,
            is_aliased=False,
            statement_id=0,
        )
        seen = {
            (
                source_export.name,
                source_export.kind,
                source_export.crossing_type,
                source_export.normalized_path,
            )
            for source_export in exports
        }
        module_key = (
            module_export.name,
            module_export.kind,
            module_export.crossing_type,
            module_export.normalized_path,
        )
        if module_key in seen:
            return exports
        return [module_export, *exports]


__all__ = [
    "SourceExtraction",
    "SourceExtractor",
]
