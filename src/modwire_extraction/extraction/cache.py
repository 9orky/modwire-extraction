from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .models import CodeMap, SourceManifest
from .serialization import (
    CodeMapSerializationError,
    deserialize_code_map,
    serialize_code_map,
)


CACHE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ExtractionCache:
    root: Path = Path()
    max_entries: int = 10
    enabled: bool = True

    def cache_path(self, cache_key: str) -> Path:
        return self.root / f"{cache_key}.json"

    def load(self, cache_key: str) -> CodeMap | None:
        path = self.cache_path(cache_key)
        if not self.enabled or not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload["schema_version"] != CACHE_SCHEMA_VERSION:
                raise CodeMapSerializationError(
                    f"Unsupported cache schema version: {payload['schema_version']}"
                )
            code_map = deserialize_code_map(
                payload["code_map"],
                cache_status="hit",
                cache_key=cache_key,
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise CodeMapSerializationError(
                f"Failed to read extraction cache entry {path}"
            ) from error

        return code_map

    def store(
        self,
        cache_key: str,
        code_map: CodeMap,
        manifest: SourceManifest,
    ) -> None:
        if not self.enabled:
            return

        self.root.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "cache_key": cache_key,
            "manifest": manifest.to_dict(),
            "code_map": serialize_code_map(code_map),
        }
        content = json.dumps(payload, sort_keys=True)
        with tempfile.NamedTemporaryFile(
            "w",
            delete=False,
            dir=self.root,
            encoding="utf-8",
        ) as temp_file:
            temp_file.write(content)
            temp_name = temp_file.name

        Path(temp_name).replace(self.cache_path(cache_key))
        self.prune()

    def prune(self) -> None:
        if self.max_entries <= 0 or not self.root.is_dir():
            return

        entries = sorted(
            (path for path in self.root.glob("*.json") if path.is_file()),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )
        for stale_path in entries[self.max_entries :]:
            stale_path.unlink(missing_ok=True)


DEFAULT_EXTRACTION_CACHE = ExtractionCache(enabled=False)
