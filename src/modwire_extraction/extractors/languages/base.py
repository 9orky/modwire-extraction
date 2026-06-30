import abc
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Literal, cast

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ..source import SourceFile


class SourceExtraction(BaseModel):
    model_config = ConfigDict(frozen=True)

    files: dict[str, SourceFile]
    files_found: int
    files_excluded: int

    def files_dict(self) -> dict[str, SourceFile]:
        return dict(self.files)


@dataclass(frozen=True)
class BatchConfig:
    size: int = 500
    parallel_threshold: int = 0
    parallel_size: int = 0
    max_workers: int = 1
    output_format: Literal["json", "jsonl"] = "json"


@dataclass(frozen=True)
class ExtractorRuntime:
    language: str
    file_extensions: tuple[str, ...]
    command: tuple[str, ...]
    script_path: Path


class SourceExtractor(abc.ABC):
    excluded_dir_names = frozenset(
        {
            ".git",
            ".hg",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            ".svn",
            ".venv",
            "__pycache__",
            "build",
            "coverage",
            "dist",
            "ignored",
            "node_modules",
            "vendor",
        }
    )

    @property
    @abc.abstractmethod
    def runtime(self) -> ExtractorRuntime:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def batch_config(self) -> BatchConfig:
        raise NotImplementedError

    def has_source_files(self, root: Path) -> bool:
        resolved_root = root.resolve()
        if not resolved_root.is_dir():
            raise ValueError(f"Source root is not a directory: {root}")

        source_paths, _ = self._discover_source_files(resolved_root)
        return bool(source_paths)

    def extract_source(self, root: Path) -> SourceExtraction:
        resolved_root = root.resolve()
        if not resolved_root.is_dir():
            raise ValueError(f"Source root is not a directory: {root}")

        source_paths, files_excluded = self._discover_source_files(resolved_root)
        files: dict[str, SourceFile] = {}
        batch_size = max(1, self.batch_config.size)

        for start in range(0, len(source_paths), batch_size):
            batch_paths = source_paths[start : start + batch_size]
            files.update(self._extract_batch(resolved_root, batch_paths))

        return SourceExtraction(
            files=files,
            files_found=len(source_paths),
            files_excluded=files_excluded,
        )

    def _discover_source_files(self, root: Path) -> tuple[list[Path], int]:
        source_paths: list[Path] = []
        files_excluded = 0
        extensions = self.runtime.file_extensions

        for current_root, dir_names, file_names in os.walk(root):
            current_path = Path(current_root)
            excluded_dirs = [
                dir_name for dir_name in dir_names if self._is_excluded_dir(dir_name)
            ]
            files_excluded += sum(
                self._count_source_files(current_path / dir_name)
                for dir_name in excluded_dirs
            )
            dir_names[:] = [
                dir_name for dir_name in dir_names if dir_name not in excluded_dirs
            ]

            for file_name in file_names:
                file_path = current_path / file_name
                if file_path.suffix.lower() in extensions:
                    source_paths.append(file_path.resolve())

        return sorted(source_paths), files_excluded

    def _count_source_files(self, root: Path) -> int:
        count = 0
        extensions = self.runtime.file_extensions
        for current_root, dir_names, file_names in os.walk(root):
            dir_names[:] = [
                dir_name
                for dir_name in dir_names
                if not self._is_excluded_dir(dir_name)
            ]
            count += sum(
                1
                for file_name in file_names
                if (Path(current_root) / file_name).suffix.lower() in extensions
            )
        return count

    def _is_excluded_dir(self, name: str) -> bool:
        return name in self.excluded_dir_names or name.startswith(".")

    def _extract_batch(self, root: Path, source_paths: list[Path]) -> dict[str, SourceFile]:
        if not source_paths:
            return {}

        runtime = self.runtime
        if not runtime.script_path.is_file():
            raise RuntimeError(
                f"{runtime.language} extractor script is missing: {runtime.script_path}"
            )
        executable = runtime.command[0]
        if shutil.which(executable) is None:
            raise RuntimeError(
                f"{runtime.language} extractor runtime is not available on PATH: "
                f"{executable}"
            )

        paths_by_source_id = {
            self._source_id_for_path(root, source_path): str(source_path)
            for source_path in source_paths
        }
        command = [
            *runtime.command,
            str(runtime.script_path),
            "--batch",
            str(root),
        ]
        if self.batch_config.output_format == "jsonl":
            command.append("--jsonl")

        result = subprocess.run(
            command,
            input=json.dumps(paths_by_source_id),
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(
                f"{runtime.language} extractor failed with exit code "
                f"{result.returncode}: {message}"
            )

        extracted = self._parse_batch_output(result.stdout)
        return {
            source_id: SourceFile.model_validate(source_file)
            for source_id, source_file in extracted.items()
        }

    def _parse_batch_output(self, output: str) -> dict[str, Any]:
        if self.batch_config.output_format == "jsonl":
            result: dict[str, Any] = {}
            for line in output.splitlines():
                if not line.strip():
                    continue
                item: Any = json.loads(line)
                if not isinstance(item, list):
                    raise RuntimeError("Extractor returned invalid JSONL batch output.")
                item_list = cast(list[Any], item)
                if len(item_list) != 2:
                    raise RuntimeError("Extractor returned invalid JSONL batch output.")
                source_id, source_file = item_list
                if not isinstance(source_id, str):
                    raise RuntimeError("Extractor returned a non-string source id.")
                result[source_id] = source_file
            return result

        parsed: Any = json.loads(output)
        if not isinstance(parsed, dict):
            raise RuntimeError("Extractor returned invalid JSON batch output.")
        return cast(dict[str, Any], parsed)

    def _source_id_for_path(self, root: Path, path: Path) -> str:
        relative_path = path.relative_to(root)
        return relative_path.with_suffix("").as_posix().strip("/")
