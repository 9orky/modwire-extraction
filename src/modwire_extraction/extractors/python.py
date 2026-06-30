from __future__ import annotations

import os
import sys
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context

from dataclasses import dataclass
from posixpath import normpath
from pathlib import Path, PurePosixPath

from .source import SourceExport, SourceFile, SourceImport
from .base import (
    ExtractionTarget,
    ExtractorProcessError,
    SourceExtraction,
    SourceExtractor,
    collect_extraction_targets,
    _extract_files,
    _join_source_id,
    _validate_source_files,
)
from .scripts.python_extractor import extract_file


def _extract_python_target(args: tuple[str, str, str]) -> tuple[str, dict[str, object]]:
    source_id, path, sources_root = args
    return source_id, extract_file(Path(path), Path(sources_root), source_id)


@dataclass(frozen=True)
class PythonSourceIndex:
    known_source_ids: set[str]
    unique_suffixes: dict[str, str | None]

    @classmethod
    def build(cls, known_source_ids: set[str]) -> PythonSourceIndex:
        suffixes: dict[str, str | None] = {}
        for source_id in known_source_ids:
            parts = source_id.split("/")
            for index in range(len(parts)):
                suffix = "/".join(parts[index:])
                previous = suffixes.get(suffix)
                if previous is None and suffix in suffixes:
                    continue
                if previous is not None and previous != source_id:
                    suffixes[suffix] = None
                    continue
                suffixes[suffix] = source_id
        return cls(known_source_ids=known_source_ids, unique_suffixes=suffixes)


@dataclass(frozen=True)
class PythonExtractor(SourceExtractor):
    language = "python"
    file_extensions = (".py",)
    command = sys.executable
    extractor_file = "python_extractor.py"
    batch_size = 500
    batch_output_format = "json"
    batch_parallel_threshold = 0
    batch_parallel_size = 500
    max_batch_parallel_workers = 1
    parallel_threshold = 50
    parallel_chunk_size = 25
    max_parallel_workers = 8

    def extract_files(
        self,
        sources_root: Path,
        exclusions: tuple[str, ...],
        source_id_prefix: str = "",
    ) -> SourceExtraction:
        if self._native_enabled():
            return self._extract_files_native(
                sources_root,
                exclusions,
                source_id_prefix=source_id_prefix,
            )
        return _extract_files(
            self,
            sources_root,
            exclusions,
            source_id_prefix=source_id_prefix,
            batch_size=self.batch_size,
        )

    def _extract_files_native(
        self,
        sources_root: Path,
        exclusions: tuple[str, ...],
        *,
        source_id_prefix: str = "",
    ) -> SourceExtraction:
        targets, files_found, files_excluded = collect_extraction_targets(
            sources_root,
            self.file_extensions,
            exclusions,
        )
        if not targets:
            return SourceExtraction(
                files={},
                files_found=files_found,
                files_excluded=files_excluded,
            )

        resolved_root = sources_root.resolve()
        items = tuple(
            (
                self.normalize_source_id(
                    _join_source_id(source_id_prefix, target.source_id)
                ),
                str(target.path.resolve()),
                str(resolved_root),
            )
            for target in targets
        )
        raw_files = self._extract_raw_files_native(items, targets, resolved_root)
        return SourceExtraction(
            files=self._source_files_from_raw_native(raw_files),
            files_found=files_found,
            files_excluded=files_excluded,
        )

    def _source_files_from_raw_native(
        self,
        raw_files: dict[str, object],
    ) -> dict[str, SourceFile]:
        result = _validate_source_files(raw_files)
        source_index = PythonSourceIndex.build(set(result))
        return {
            source_id: self._normalize_source_file_with_index(
                source_id,
                source_file,
                source_index,
            )
            for source_id, source_file in result.items()
        }

    def _normalize_source_file_with_index(
        self,
        source_id: str,
        source_file: SourceFile,
        source_index: PythonSourceIndex,
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
        source_index: PythonSourceIndex,
    ) -> SourceImport:
        normalized_path = self._normalize_relative_import(source_id, source_import)
        crossing_type = source_import.crossing_type
        if source_import.imported_name and source_import.imported_name != "*":
            module_import_path = "/".join(
                part for part in (normalized_path, source_import.imported_name) if part
            )
            module_source_id = self._known_source_id_indexed(
                module_import_path,
                source_index,
            )
            if module_source_id in source_index.known_source_ids:
                normalized_path = module_source_id
                crossing_type = "module"
            else:
                normalized_path = self._known_source_id_indexed(
                    normalized_path,
                    source_index,
                )
        else:
            normalized_path = self._known_source_id_indexed(
                normalized_path,
                source_index,
            )

        return SourceImport.model_construct(
            path=source_import.path,
            is_relative=source_import.is_relative,
            normalized_path=normalized_path,
            imported_name=source_import.imported_name,
            is_aliased=source_import.is_aliased,
            crossing_type=crossing_type,
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
        source_index: PythonSourceIndex,
    ) -> SourceExport:
        normalized_path = source_export.normalized_path
        if source_export.is_relative:
            level = len(source_export.path) - len(source_export.path.lstrip("."))
            module_path = source_export.path[level:].replace(".", "/").strip("/")
            package_path = PurePosixPath(source_id).parent
            for _ in range(max(level - 1, 0)):
                package_path = package_path.parent
            normalized_path = normpath(
                "/".join(
                    part for part in (package_path.as_posix(), module_path) if part
                )
            )

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
        source_index: PythonSourceIndex,
    ) -> str:
        candidates = (normalized_path, f"{normalized_path}/__init__")
        for candidate in candidates:
            if candidate in source_index.known_source_ids:
                return candidate
            match = source_index.unique_suffixes.get(candidate)
            if match is not None:
                return match
        return normalized_path

    def _extract_raw_files_native(
        self,
        items: tuple[tuple[str, str, str], ...],
        targets: tuple[ExtractionTarget, ...],
        sources_root: Path,
    ) -> dict[str, object]:
        worker_count = self._worker_count(len(items))
        try:
            if worker_count <= 1:
                return dict(_extract_python_target(item) for item in items)
            try:
                context = get_context("fork")
                with ProcessPoolExecutor(
                    max_workers=worker_count,
                    mp_context=context,
                ) as pool:
                    return dict(
                        pool.map(
                            _extract_python_target,
                            items,
                            chunksize=self.parallel_chunk_size,
                        )
                    )
            except OSError:
                return dict(_extract_python_target(item) for item in items)
        except Exception as exc:
            raise ExtractorProcessError(
                self._format_native_error(exc, targets, sources_root, worker_count)
            ) from exc

    def _worker_count(self, file_count: int) -> int:
        if os.name != "posix" or file_count < self.parallel_threshold:
            return 1
        configured = os.environ.get("MODWIRE_PYTHON_EXTRACTOR_WORKERS")
        if configured is not None:
            try:
                requested_workers = int(configured)
            except ValueError as exc:
                raise ValueError(
                    "MODWIRE_PYTHON_EXTRACTOR_WORKERS must be an integer"
                ) from exc
            if requested_workers <= 0:
                return 1
            return min(requested_workers, file_count)
        return min(os.cpu_count() or 1, self.max_parallel_workers, file_count)

    def _native_enabled(self) -> bool:
        return os.environ.get("MODWIRE_PYTHON_EXTRACTOR_NATIVE", "1") != "0"

    def _format_native_error(
        self,
        error: Exception,
        targets: tuple[ExtractionTarget, ...],
        sources_root: Path,
        worker_count: int,
    ) -> str:
        return "\n".join(
            (
                "Native Python extractor failed.",
                f"language: {self.language}",
                f"source root: {sources_root.resolve()}",
                f"files: {len(targets)}",
                f"workers: {worker_count}",
                f"{type(error).__name__}: {error}",
            )
        )

    def normalize_import(
        self,
        source_id: str,
        source_import: SourceImport,
        known_source_ids: set[str],
    ) -> SourceImport:
        normalized_path = self._normalize_relative_import(source_id, source_import)
        crossing_type = source_import.crossing_type
        if source_import.imported_name and source_import.imported_name != "*":
            module_import_path = "/".join(
                part for part in (normalized_path, source_import.imported_name) if part
            )
            module_source_id = self._known_source_id(module_import_path, known_source_ids)
            if module_source_id in known_source_ids:
                normalized_path = module_source_id
                crossing_type = "module"
            else:
                normalized_path = self._known_source_id(normalized_path, known_source_ids)
        else:
            normalized_path = self._known_source_id(normalized_path, known_source_ids)

        return SourceImport.model_construct(
            path=source_import.path,
            is_relative=source_import.is_relative,
            normalized_path=normalized_path,
            imported_name=source_import.imported_name,
            is_aliased=source_import.is_aliased,
            crossing_type=crossing_type,
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
        if source_export.is_relative:
            level = len(source_export.path) - len(source_export.path.lstrip("."))
            module_path = source_export.path[level:].replace(".", "/").strip("/")
            package_path = PurePosixPath(source_id).parent
            for _ in range(max(level - 1, 0)):
                package_path = package_path.parent
            normalized_path = normpath(
                "/".join(
                    part for part in (package_path.as_posix(), module_path) if part
                )
            )

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

    def _normalize_relative_import(
        self,
        source_id: str,
        source_import: SourceImport,
    ) -> str:
        if not source_import.is_relative:
            return source_import.normalized_path

        level = len(source_import.path) - len(source_import.path.lstrip("."))
        module_path = source_import.path[level:].replace(".", "/").strip("/")
        package_path = PurePosixPath(source_id).parent
        for _ in range(max(level - 1, 0)):
            package_path = package_path.parent

        return normpath(
            "/".join(part for part in (package_path.as_posix(), module_path) if part)
        )

    def _known_source_id(
        self,
        normalized_path: str,
        known_source_ids: set[str],
    ) -> str:
        candidates = (normalized_path, f"{normalized_path}/__init__")
        for candidate in candidates:
            if candidate in known_source_ids:
                return candidate
            match = self._unique_suffix_match(candidate, known_source_ids)
            if match is not None:
                return match
        return normalized_path

    def _normalized_join_key(
        self,
        normalized_path: str,
        source_import: SourceImport,
    ) -> str:
        if not source_import.join_key or not normalized_path:
            return ""
        parent = PurePosixPath(normalized_path).parent.as_posix()
        return "" if parent == "." else parent

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


__all__ = ["PythonExtractor"]
