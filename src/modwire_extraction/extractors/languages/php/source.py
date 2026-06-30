from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from ...source import SourceExport, SourceFile, SourceImport
from ...base import (
    SourceExtraction,
    SourceExtractor,
)


@dataclass(frozen=True)
class PhpExtractor(SourceExtractor):
    language = "php"
    file_extensions = (".php",)
    command = "php"
    extractor_file = "php_extractor.php"
    batch_size = 500
    batch_output_format = "jsonl"
    batch_parallel_threshold = 500
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

    def normalize_source_files(
        self,
        files: dict[str, SourceFile],
    ) -> dict[str, SourceFile]:
        source_index = PhpSourceIndex.build(set(files))
        return {
            source_id: self._normalize_source_file_with_index(
                source_id,
                source_file,
                source_index,
            )
            for source_id, source_file in files.items()
        }

    def _normalize_source_file_with_index(
        self,
        source_id: str,
        source_file: SourceFile,
        source_index: PhpSourceIndex,
    ) -> SourceFile:
        exports = [
            self._normalize_export_with_index(source_id, source_export, source_index)
            for source_export in source_file.exports
        ]
        exports = self._with_module_export(source_id, exports)

        return SourceFile.model_construct(
            imports=[
                self._normalize_import_with_index(
                    source_id,
                    source_import,
                    source_index,
                )
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

    def _normalize_import_with_index(
        self,
        source_id: str,
        source_import: SourceImport,
        source_index: PhpSourceIndex,
    ) -> SourceImport:
        normalized_path = self._known_source_id_indexed(
            source_import.normalized_path,
            source_index,
        )
        return SourceImport.model_construct(
            path=source_import.path,
            is_relative=source_import.is_relative,
            normalized_path=normalized_path,
            imported_name=source_import.imported_name,
            is_aliased=source_import.is_aliased,
            crossing_type=source_import.crossing_type,
            file_barrier_crossed=(
                source_import.file_barrier_crossed
                and normalized_path in source_index.known_source_ids
            ),
            statement_id=source_import.statement_id,
            join_key=self._normalized_join_key(normalized_path, source_import),
            uses_joined_import=source_import.uses_joined_import,
            imported_symbols=source_import.imported_symbols,
        )

    def _normalize_export_with_index(
        self,
        source_id: str,
        source_export: SourceExport,
        source_index: PhpSourceIndex,
    ) -> SourceExport:
        normalized_path = source_export.normalized_path
        if normalized_path:
            normalized_path = self._known_source_id_indexed(
                normalized_path,
                source_index,
            )

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

    def _known_source_id_indexed(
        self,
        normalized_path: str,
        source_index: PhpSourceIndex,
    ) -> str:
        candidates = (normalized_path, *self._php_source_id_candidates(normalized_path))
        for candidate in candidates:
            if candidate in source_index.known_source_ids:
                return candidate
            match = source_index.unique_suffixes.get(candidate)
            if match is not None:
                return match

        namespace_match = self._namespace_source_id_indexed(
            normalized_path,
            source_index,
        )
        if namespace_match is not None:
            return namespace_match
        return normalized_path

    def _namespace_source_id_indexed(
        self,
        normalized_path: str,
        source_index: PhpSourceIndex,
    ) -> str | None:
        matches: set[str] = set()
        ambiguous = False
        for candidate in self._php_source_id_candidates(normalized_path):
            namespace_path = self._source_parent(candidate)
            if namespace_path == ".":
                continue
            match = source_index.namespace_suffixes.get(namespace_path)
            if match is None:
                if namespace_path in source_index.namespace_suffixes:
                    ambiguous = True
                continue
            matches.add(match)
        return matches.pop() if len(matches) == 1 and not ambiguous else None

    def normalize_import(
        self,
        source_id: str,
        source_import: SourceImport,
        known_source_ids: set[str],
    ) -> SourceImport:
        normalized_path = self._known_source_id(
            source_import.normalized_path,
            known_source_ids,
        )
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
            join_key=self._normalized_join_key(normalized_path, source_import),
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
        if normalized_path:
            normalized_path = self._known_source_id(normalized_path, known_source_ids)

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

    def _normalized_join_key(
        self,
        normalized_path: str,
        source_import: SourceImport,
    ) -> str:
        if not source_import.join_key or not normalized_path:
            return ""
        parts = normalized_path.split("/")
        return "/".join(parts[:-1])

    def _known_source_id(
        self,
        normalized_path: str,
        known_source_ids: set[str],
    ) -> str:
        candidates = (normalized_path, *self._php_source_id_candidates(normalized_path))
        for candidate in candidates:
            if candidate in known_source_ids:
                return candidate
            match = self._unique_suffix_match(candidate, known_source_ids)
            if match is not None:
                return match

        namespace_match = self._namespace_source_id(normalized_path, known_source_ids)
        if namespace_match is not None:
            return namespace_match
        return normalized_path

    def _php_source_id_candidates(self, normalized_path: str) -> tuple[str, ...]:
        parts = [self._source_part(part) for part in normalized_path.split("/") if part]
        return tuple("/".join(parts[index:]) for index in range(len(parts)))

    def _namespace_source_id(
        self,
        normalized_path: str,
        known_source_ids: set[str],
    ) -> str | None:
        namespace_matches: list[str] = []
        for candidate in self._php_source_id_candidates(normalized_path):
            namespace_path = PurePosixPath(candidate).parent.as_posix()
            if not namespace_path or namespace_path == ".":
                continue
            namespace_suffix = f"/{namespace_path}"
            namespace_matches.extend(
                source_id
                for source_id in known_source_ids
                if self._source_parent(source_id) == namespace_path
                or self._source_parent(source_id).endswith(namespace_suffix)
            )

        matches = sorted(set(namespace_matches))
        return matches[0] if len(matches) == 1 else None

    def _unique_suffix_match(
        self,
        candidate: str,
        known_source_ids: set[str],
    ) -> str | None:
        suffix = f"/{candidate}"
        matches = sorted(
            source_id
            for source_id in known_source_ids
            if source_id == candidate or source_id.endswith(suffix)
        )
        return matches[0] if len(matches) == 1 else None

    def _source_part(self, value: str) -> str:
        return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()

    @staticmethod
    def _source_parent(source_id: str) -> str:
        parent = source_id.rpartition("/")[0]
        return parent or "."


__all__ = ["PhpExtractor"]
