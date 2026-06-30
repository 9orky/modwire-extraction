from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from subprocess import PIPE, CalledProcessError, Popen, run
from typing import Protocol

from pydantic import TypeAdapter

from .source import (
    SourceAbstractClass,
    SourceCall,
    SourceCallable,
    SourceClass,
    SourceClassMethod,
    SourceClassProperty,
    SourceExport,
    SourceFile,
    SourceFunction,
    SourceImport,
    SourceImportedSymbol,
    SourceInterface,
    SourceParameter,
    SourceSignature,
    SourceType,
    SourceValue,
)
from .resources import extractor_script_path

_SOURCE_FILES_ADAPTER = TypeAdapter(dict[str, SourceFile])


@dataclass(frozen=True)
class SourceExtraction:
    files: dict[str, SourceFile]
    files_found: int
    files_excluded: int


@dataclass(frozen=True)
class ExtractionTarget:
    source_id: str
    path: Path


class ExtractorProcessError(RuntimeError):
    """Raised when a language extractor subprocess fails."""


class SourceExtractor(Protocol):
    language: str
    file_extensions: tuple[str, ...]
    command: str
    extractor_file: str
    batch_output_format: str
    batch_parallel_threshold: int
    batch_parallel_size: int
    max_batch_parallel_workers: int

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
        )

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


def _extract_files(
    extractor: SourceExtractor,
    sources_root: Path,
    exclusions: tuple[str, ...],
    *,
    source_id_prefix: str = "",
    batch_size: int = 0,
) -> SourceExtraction:
    targets, files_found, files_excluded = collect_extraction_targets(
        sources_root,
        extractor.file_extensions,
        exclusions,
    )
    if not targets:
        return SourceExtraction(
            files={},
            files_found=files_found,
            files_excluded=files_excluded,
        )

    input_data = {
        extractor.normalize_source_id(
            _join_source_id(source_id_prefix, target.source_id)
        ): str(target.path.resolve())
        for target in targets
    }
    with extractor_script_path(extractor.extractor_file) as script:
        cmd = [extractor.command, str(script), "--batch", str(sources_root.resolve())]
        if getattr(extractor, "batch_output_format", "json") == "jsonl":
            raw_files = _jsonl_from_output_in_parallel(
                [*cmd, "--jsonl"],
                input_data,
                language=extractor.language,
                sources_root=sources_root,
                batch_size=getattr(extractor, "batch_parallel_size", batch_size),
                parallel_threshold=getattr(
                    extractor,
                    "batch_parallel_threshold",
                    0,
                ),
                max_workers=getattr(extractor, "max_batch_parallel_workers", 1),
            )
        elif batch_size:
            raw_files = _json_from_output_in_batches(
                cmd,
                input_data,
                language=extractor.language,
                sources_root=sources_root,
                batch_size=batch_size,
            )
        else:
            raw_files = _json_from_output(
                cmd,
                json.dumps(input_data),
                language=extractor.language,
                sources_root=sources_root,
                file_count=len(input_data),
            )
    result = _source_files_from_raw(extractor, raw_files)

    return SourceExtraction(
        files=result,
        files_found=files_found,
        files_excluded=files_excluded,
    )


def _source_files_from_raw(
    extractor: SourceExtractor,
    raw_files: dict[str, object],
) -> dict[str, SourceFile]:
    files = _validate_source_files(raw_files)
    return extractor.normalize_source_files(files)


def _validate_source_files(raw_files: dict[str, object]) -> dict[str, SourceFile]:
    if os.environ.get("MODWIRE_VALIDATE_EXTRACTOR_OUTPUT") == "1":
        return _SOURCE_FILES_ADAPTER.validate_python(raw_files)
    return {
        source_id: _construct_source_file(source_file)
        for source_id, source_file in raw_files.items()
    }


def _construct_source_file(source_file: object) -> SourceFile:
    if isinstance(source_file, SourceFile):
        return source_file
    if not isinstance(source_file, dict):
        return SourceFile.model_validate(source_file)
    return SourceFile.model_construct(
        imports=[
            SourceImport.model_construct(
                **{
                    **source_import,
                    "imported_symbols": _construct_models(
                        SourceImportedSymbol,
                        source_import.get("imported_symbols", []),
                    ),
                }
            )
            for source_import in source_file.get("imports", [])
        ],
        exports=_construct_models(SourceExport, source_file.get("exports", [])),
        classes=[
            SourceClass.model_construct(
                **{
                    **source_class,
                    "methods": _construct_models(
                        SourceClassMethod,
                        source_class.get("methods", []),
                    ),
                    "properties": _construct_models(
                        SourceClassProperty,
                        source_class.get("properties", []),
                    ),
                }
            )
            for source_class in source_file.get("classes", [])
        ],
        interfaces=[
            SourceInterface.model_construct(
                **{
                    **source_interface,
                    "methods": _construct_models(
                        SourceClassMethod,
                        source_interface.get("methods", []),
                    ),
                    "properties": _construct_models(
                        SourceClassProperty,
                        source_interface.get("properties", []),
                    ),
                    "signatures": _construct_models(
                        SourceSignature,
                        source_interface.get("signatures", []),
                    ),
                }
            )
            for source_interface in source_file.get("interfaces", [])
        ],
        types=[
            SourceType.model_construct(
                **{
                    **source_type,
                    "properties": _construct_models(
                        SourceClassProperty,
                        source_type.get("properties", []),
                    ),
                    "signatures": _construct_models(
                        SourceSignature,
                        source_type.get("signatures", []),
                    ),
                }
            )
            for source_type in source_file.get("types", [])
        ],
        abstract_classes=[
            SourceAbstractClass.model_construct(
                **{
                    **source_class,
                    "abstract_methods": _construct_models(
                        SourceClassMethod,
                        source_class.get("abstract_methods", []),
                    ),
                    "concrete_methods": _construct_models(
                        SourceClassMethod,
                        source_class.get("concrete_methods", []),
                    ),
                    "properties": _construct_models(
                        SourceClassProperty,
                        source_class.get("properties", []),
                    ),
                }
            )
            for source_class in source_file.get("abstract_classes", [])
        ],
        functions=_construct_models(SourceFunction, source_file.get("functions", [])),
        values=_construct_models(SourceValue, source_file.get("values", [])),
        callables=[
            SourceCallable.model_construct(
                **{
                    **source_callable,
                    "parameters": _construct_models(
                        SourceParameter,
                        source_callable.get("parameters", []),
                    ),
                }
            )
            for source_callable in source_file.get("callables", [])
        ],
        calls=_construct_models(SourceCall, source_file.get("calls", [])),
        line_count=source_file.get("line_count", 0),
        code_line_count=source_file.get("code_line_count", 0),
        public_symbol_count=source_file.get("public_symbol_count", 0),
    )


def _construct_models(model, values: object) -> list:
    if not isinstance(values, list):
        return []
    return [
        value if isinstance(value, model) else model.model_construct(**value)
        for value in values
        if isinstance(value, dict) or isinstance(value, model)
    ]


def collect_extraction_targets(
    sources_root: Path,
    file_extensions: tuple[str, ...],
    exclusions: tuple[str, ...],
) -> tuple[tuple[ExtractionTarget, ...], int, int]:
    directory_exclusions, file_exclusions = _partition_exclusions(
        exclusions,
        file_extensions,
    )
    targets: list[ExtractionTarget] = []
    files_found = 0
    files_excluded = 0

    def walk(directory: Path, relative_dir: str = "") -> None:
        nonlocal files_found, files_excluded
        directories: list[tuple[str, Path]] = []
        files: list[tuple[str, Path]] = []

        for entry in sorted(directory.iterdir(), key=lambda path: path.name):
            source_id = (
                f"{relative_dir}/{entry.name}" if relative_dir else entry.name
            )
            if entry.is_dir() and not entry.is_symlink():
                if _matches_directory_exclusion(source_id, directory_exclusions):
                    # Exact file counts would require descending into the pruned tree.
                    files_found += 1
                    files_excluded += 1
                    continue
                directories.append((source_id, entry))
                continue

            if entry.is_file() and entry.suffix in file_extensions:
                files.append((source_id, entry))

        for source_id, path in files:
            files_found += 1
            if any(
                _matches_exclusion(source_id, exclusion)
                for exclusion in file_exclusions
            ):
                files_excluded += 1
                continue

            targets.append(ExtractionTarget(source_id, path))

        for source_id, path in directories:
            walk(path, source_id)

    walk(sources_root)

    return tuple(targets), files_found, files_excluded


def _json_from_output(
    cmd: list[str],
    input_json: str = "",
    *,
    language: str = "",
    sources_root: Path | None = None,
    file_count: int | None = None,
) -> dict:
    try:
        output_json = run(
            cmd,
            capture_output=True,
            text=True,
            input=input_json,
            check=True,
        ).stdout
    except CalledProcessError as e:
        raise ExtractorProcessError(
            _format_process_error(e, language, sources_root, file_count)
        ) from e

    try:
        return json.loads(output_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON from output: {output_json}") from e


def _json_from_output_in_batches(
    cmd: list[str],
    input_data: dict[str, str],
    *,
    language: str,
    sources_root: Path,
    batch_size: int,
) -> dict:
    result: dict[str, object] = {}
    items = tuple(input_data.items())
    for start in range(0, len(items), batch_size):
        chunk = dict(items[start : start + batch_size])
        raw_files = _json_from_output(
            cmd,
            json.dumps(chunk),
            language=language,
            sources_root=sources_root,
            file_count=len(chunk),
        )
        result.update(raw_files)
    return result


def _jsonl_from_output_in_parallel(
    cmd: list[str],
    input_data: dict[str, str],
    *,
    language: str,
    sources_root: Path,
    batch_size: int,
    parallel_threshold: int,
    max_workers: int,
) -> dict:
    worker_count = _jsonl_worker_count(
        len(input_data),
        batch_size=batch_size,
        parallel_threshold=parallel_threshold,
        max_workers=max_workers,
    )
    if worker_count <= 1:
        return _jsonl_from_output(
            cmd,
            json.dumps(input_data),
            language=language,
            sources_root=sources_root,
            file_count=len(input_data),
        )

    result: dict[str, object] = {}
    items = tuple(input_data.items())
    chunks = tuple(
        dict(items[start : start + batch_size])
        for start in range(0, len(items), batch_size)
    )
    with ThreadPoolExecutor(max_workers=min(worker_count, len(chunks))) as pool:
        for raw_files in pool.map(
            lambda chunk: _jsonl_from_output(
                cmd,
                json.dumps(chunk),
                language=language,
                sources_root=sources_root,
                file_count=len(chunk),
            ),
            chunks,
        ):
            result.update(raw_files)
    return result


def _jsonl_worker_count(
    file_count: int,
    *,
    batch_size: int,
    parallel_threshold: int,
    max_workers: int,
) -> int:
    if file_count < parallel_threshold or batch_size <= 0 or max_workers <= 1:
        return 1
    configured = os.environ.get("MODWIRE_BATCH_EXTRACTOR_WORKERS")
    if configured is not None:
        try:
            requested_workers = int(configured)
        except ValueError as exc:
            raise ValueError(
                "MODWIRE_BATCH_EXTRACTOR_WORKERS must be an integer"
            ) from exc
        if requested_workers <= 0:
            return 1
        return min(requested_workers, file_count)
    return min(max_workers, file_count)


def _jsonl_from_output(
    cmd: list[str],
    input_json: str = "",
    *,
    language: str = "",
    sources_root: Path | None = None,
    file_count: int | None = None,
) -> dict:
    process = Popen(
        cmd,
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
        text=True,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    process.stdin.write(input_json)
    process.stdin.close()

    result: dict[str, object] = {}
    output_tail: list[str] = []
    try:
        for line in process.stdout:
            stripped = line.strip()
            if not stripped:
                continue
            output_tail.append(stripped)
            output_tail = output_tail[-20:]
            try:
                source_id, source_file = json.loads(stripped)
            except json.JSONDecodeError as exc:
                process.kill()
                raise ValueError(f"Failed to parse JSONL from output: {stripped}") from exc
            if not isinstance(source_id, str):
                process.kill()
                raise ValueError(f"Expected JSONL source id to be a string: {stripped}")
            result[source_id] = source_file
    finally:
        process.stdout.close()

    stderr = ""
    if process.stderr is not None:
        stderr = process.stderr.read()
        process.stderr.close()
    return_code = process.wait()
    if return_code != 0:
        raise ExtractorProcessError(
            _format_process_error(
                CalledProcessError(
                    return_code,
                    cmd,
                    output="\n".join(output_tail),
                    stderr=stderr,
                ),
                language,
                sources_root,
                file_count,
            )
        )
    return result


def _format_process_error(
    error: CalledProcessError,
    language: str,
    sources_root: Path | None,
    file_count: int | None,
) -> str:
    lines = [
        "Extractor subprocess failed.",
        f"command: {_format_command(error.cmd)}",
        f"exit code: {error.returncode}",
    ]
    if language:
        lines.append(f"language: {language}")
    if sources_root is not None:
        lines.append(f"source root: {sources_root.resolve()}")
    if file_count is not None:
        lines.append(f"files: {file_count}")

    stdout = _text_tail(error.stdout or error.output)
    stderr = _text_tail(error.stderr)
    if stdout:
        lines.extend(("stdout tail:", stdout))
    if stderr:
        lines.extend(("stderr tail:", stderr))
    return "\n".join(lines)


def _format_command(cmd: object) -> str:
    if isinstance(cmd, (list, tuple)):
        return " ".join(str(part) for part in cmd)
    return str(cmd)


def _text_tail(value: object, max_lines: int = 20) -> str:
    if not isinstance(value, str):
        return ""
    lines = value.strip().splitlines()
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    return "\n".join(lines)


def _matches_exclusion(source_id: str, exclusion: str) -> bool:
    normalized = exclusion.replace("\\", "/").strip().strip("/")
    if not normalized:
        return False

    if _matches_path_pattern(source_id, normalized):
        return True

    has_glob = any(char in normalized for char in "*?[")
    if not normalized or has_glob:
        return False

    return source_id.startswith(f"{normalized}/")


def _partition_exclusions(
    exclusions: tuple[str, ...],
    file_extensions: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    directory_exclusions = []
    file_exclusions = []
    for exclusion in exclusions:
        normalized = exclusion.replace("\\", "/").strip()
        if not normalized:
            continue
        if _is_recursive_directory_exclusion(normalized, file_extensions):
            directory_exclusions.append(_directory_exclusion_pattern(normalized))
        else:
            file_exclusions.append(normalized.strip("/"))
    return tuple(directory_exclusions), tuple(file_exclusions)


def _is_recursive_directory_exclusion(
    exclusion: str,
    file_extensions: tuple[str, ...],
) -> bool:
    normalized = exclusion.strip("/")
    if not normalized:
        return False
    if exclusion.endswith("/") or normalized.endswith("/**"):
        return True
    if any(char in normalized for char in "*?["):
        return False
    return not normalized.endswith(file_extensions)


def _directory_exclusion_pattern(exclusion: str) -> str:
    normalized = exclusion.strip("/")
    if normalized.endswith("/**"):
        return normalized[:-3].rstrip("/")
    return normalized


def _matches_directory_exclusion(
    source_id: str,
    directory_exclusions: tuple[str, ...],
) -> bool:
    for exclusion in directory_exclusions:
        if _matches_path_pattern(source_id, exclusion):
            return True
        if "/" not in exclusion and not any(char in exclusion for char in "*?["):
            if Path(source_id).name == exclusion:
                return True
    return False


def _matches_path_pattern(source_id: str, pattern: str) -> bool:
    if fnmatch(source_id, pattern):
        return True
    if pattern.startswith("**/") and fnmatch(source_id, pattern[3:]):
        return True
    return False


def _join_source_id(prefix: str, source_id: str) -> str:
    normalized_prefix = prefix.replace("\\", "/").strip().strip("/")
    normalized_source_id = source_id.replace("\\", "/").strip().strip("/")
    if not normalized_prefix:
        return normalized_source_id
    if not normalized_source_id:
        return normalized_prefix
    return f"{normalized_prefix}/{normalized_source_id}"


__all__ = [
    "ExtractorProcessError",
    "ExtractionTarget",
    "SourceExtraction",
    "SourceExtractor",
]
