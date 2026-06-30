from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


SourceIdMode = Literal["relative_to_sources_root", "relative_to_workspace_root"]


@dataclass(frozen=True)
class SourceRoots:
    workspace_root: Path = Path()
    source_id_root: str = ""
    source_id_mode: SourceIdMode = "relative_to_sources_root"


DEFAULT_SOURCE_ROOTS = SourceRoots()


def source_id_prefix(
    *,
    sources_root: Path,
    source_roots: SourceRoots,
) -> str:
    if source_roots.source_id_root:
        return normalize_path_text(source_roots.source_id_root)

    if source_roots.source_id_mode == "relative_to_sources_root":
        return ""

    if source_roots.source_id_mode != "relative_to_workspace_root":
        raise ValueError(f"Unsupported source_id_mode: {source_roots.source_id_mode}")

    if not has_workspace_root(source_roots):
        raise ValueError(
            "source_roots.workspace_root is required when source_id_mode is "
            "'relative_to_workspace_root'"
        )

    try:
        return (
            sources_root.resolve()
            .relative_to(source_roots.workspace_root.resolve())
            .as_posix()
        )
    except ValueError as error:
        raise ValueError(
            "sources_root must be inside source_roots.workspace_root"
        ) from error


def normalize_exclusions(
    exclusions: tuple[str, ...],
    *,
    sources_root: Path,
    source_roots: SourceRoots,
) -> tuple[str, ...]:
    source_prefix = ""
    if has_workspace_root(source_roots):
        try:
            source_prefix = (
                sources_root.resolve()
                .relative_to(source_roots.workspace_root.resolve())
                .as_posix()
            )
        except ValueError:
            source_prefix = ""

    normalized_exclusions = []
    for exclusion in exclusions:
        normalized = normalize_path_text(exclusion)
        if not normalized:
            continue
        if source_prefix and normalized == source_prefix:
            normalized = ""
        elif source_prefix and normalized.startswith(f"{source_prefix}/"):
            normalized = normalized[len(source_prefix) + 1 :]
        if normalized and normalized not in normalized_exclusions:
            normalized_exclusions.append(normalized)

    return tuple(normalized_exclusions)


def join_source_id(prefix: str, source_id: str) -> str:
    normalized_prefix = normalize_path_text(prefix)
    normalized_source_id = normalize_path_text(source_id)
    if not normalized_prefix:
        return normalized_source_id
    if not normalized_source_id:
        return normalized_prefix
    return f"{normalized_prefix}/{normalized_source_id}"


def normalize_path_text(value: str | Path) -> str:
    return str(value).replace("\\", "/").strip().strip("/")


def has_workspace_root(source_roots: SourceRoots) -> bool:
    return normalize_path_text(source_roots.workspace_root) not in ("", ".")
