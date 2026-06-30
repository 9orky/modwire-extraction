from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .._version import __version__
from ..extractors import collect_extraction_targets, load_extractor
from ..extractors.resources import extractor_script_path
from .roots import (
    DEFAULT_SOURCE_ROOTS,
    SourceIdMode,
    SourceRoots,
    has_workspace_root,
    join_source_id,
    normalize_exclusions,
    source_id_prefix,
)


@dataclass(frozen=True)
class SourceManifestEntry:
    source_id: str
    path: Path
    size: int
    mtime_ns: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "path": str(self.path),
            "size": self.size,
            "mtime_ns": self.mtime_ns,
        }


@dataclass(frozen=True)
class SourceManifest:
    language: str
    workspace_root: Path
    sources_root: Path
    source_id_root: str
    source_id_mode: SourceIdMode
    source_id_prefix: str
    exclusions: tuple[str, ...]
    file_extensions: tuple[str, ...]
    runtime_command: str
    runtime_path: str
    runtime_mtime_ns: int
    extractor_file: str
    extractor_path: Path
    extractor_mtime_ns: int
    modwire_version: str
    files_found: int
    files_checked: int
    files_excluded: int
    entries: tuple[SourceManifestEntry, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "workspace_root": str(self.workspace_root),
            "sources_root": str(self.sources_root),
            "source_id_root": self.source_id_root,
            "source_id_mode": self.source_id_mode,
            "source_id_prefix": self.source_id_prefix,
            "exclusions": list(self.exclusions),
            "file_extensions": list(self.file_extensions),
            "runtime_command": self.runtime_command,
            "runtime_path": self.runtime_path,
            "runtime_mtime_ns": self.runtime_mtime_ns,
            "extractor_file": self.extractor_file,
            "extractor_path": str(self.extractor_path),
            "extractor_mtime_ns": self.extractor_mtime_ns,
            "modwire_version": self.modwire_version,
            "files_found": self.files_found,
            "files_checked": self.files_checked,
            "files_excluded": self.files_excluded,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def fingerprint(self) -> str:
        return manifest_fingerprint(self)


def discover_sources(
    language: str,
    sources_root: Path,
    exclusions: tuple[str, ...] = (),
    *,
    source_roots: SourceRoots = DEFAULT_SOURCE_ROOTS,
) -> SourceManifest:
    """Return the source manifest using the same traversal as extraction."""
    assert sources_root.is_dir(), f"Project root {sources_root} is not a directory"

    extractor = load_extractor(language)
    normalized_exclusions = normalize_exclusions(
        exclusions,
        sources_root=sources_root,
        source_roots=source_roots,
    )
    prefix = source_id_prefix(
        sources_root=sources_root,
        source_roots=source_roots,
    )
    targets, files_found, files_excluded = collect_extraction_targets(
        sources_root,
        extractor.file_extensions,
        normalized_exclusions,
    )
    entries = []
    for target in targets:
        stat = target.path.stat()
        entries.append(
            SourceManifestEntry(
                source_id=extractor.normalize_source_id(
                    join_source_id(prefix, target.source_id)
                ),
                path=target.path.resolve(),
                size=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
            )
        )
    runtime_path = shutil.which(extractor.command) or ""
    runtime_mtime_ns = 0
    if runtime_path != "":
        runtime_mtime_ns = Path(runtime_path).stat().st_mtime_ns

    with extractor_script_path(extractor.extractor_file) as extractor_path:
        extractor_mtime_ns = extractor_path.stat().st_mtime_ns

    return SourceManifest(
        language=language,
        workspace_root=(
            source_roots.workspace_root.resolve()
            if has_workspace_root(source_roots)
            else Path()
        ),
        sources_root=sources_root.resolve(),
        source_id_root=source_roots.source_id_root,
        source_id_mode=source_roots.source_id_mode,
        source_id_prefix=prefix,
        exclusions=normalized_exclusions,
        file_extensions=extractor.file_extensions,
        runtime_command=extractor.command,
        runtime_path=runtime_path,
        runtime_mtime_ns=runtime_mtime_ns,
        extractor_file=extractor.extractor_file,
        extractor_path=extractor_path,
        extractor_mtime_ns=extractor_mtime_ns,
        modwire_version=__version__,
        files_found=files_found,
        files_checked=len(entries),
        files_excluded=files_excluded,
        entries=tuple(entries),
    )


def manifest_fingerprint(manifest: SourceManifest) -> str:
    payload = json.dumps(manifest.to_dict(), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
