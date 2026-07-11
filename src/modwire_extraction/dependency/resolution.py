from __future__ import annotations

import re

from ..extractors.source import SourceFile, SourceImport
from ..identity import FileId


def resolve_imports(
    files: dict[FileId, SourceFile],
) -> dict[FileId, SourceFile]:
    modules: list[tuple[str, FileId]] = []
    symbols: list[tuple[str, str, FileId]] = []

    for file_id, source_file in files.items():
        module = _normalize(source_file.module_id)
        modules.append((module, file_id))
        parent = module.rsplit("/", 1)[0] if "/" in module else ""
        for exported in source_file.exports:
            symbols.append((parent, exported.name.casefold(), file_id))

    return {
        file_id: source_file.model_copy(
            update={
                "imports": [
                    _resolve_import(imported, modules, symbols)
                    for imported in source_file.imports
                ]
            }
        )
        for file_id, source_file in files.items()
    }


def _resolve_import(
    imported: SourceImport,
    modules: list[tuple[str, FileId]],
    symbols: list[tuple[str, str, FileId]],
) -> SourceImport:
    specifier = _normalize(imported.normalized_path)
    candidates = {
        file_id
        for module, file_id in modules
        if _same_suffix(module, specifier)
    }

    if imported.crossing_type == "symbol" and imported.imported_symbols:
        symbol_names = {symbol.name.casefold() for symbol in imported.imported_symbols}
        imported_parent = _normalize(imported.join_key)
        candidates.update(
            file_id
            for module_parent, symbol_name, file_id in symbols
            if symbol_name in symbol_names
            and _same_suffix(module_parent, imported_parent)
        )

    if len(candidates) == 1:
        return imported.model_copy(
            update={
                "resolution": "resolved",
                "target_file_id": next(iter(candidates)),
            }
        )

    return imported.model_copy(
        update={
            "resolution": (
                "unresolved" if candidates or imported.is_relative else "external"
            ),
            "target_file_id": None,
        }
    )


def _normalize(value: str) -> str:
    parts = str(value).replace("\\", "/").strip("/").split("/")
    return "/".join(re.sub(r"[^a-z0-9]", "", part.casefold()) for part in parts)


def _same_suffix(left: str, right: str) -> bool:
    if not left or not right:
        return left == right
    left_parts = left.split("/")
    right_parts = right.split("/")
    shared = 0
    for left_part, right_part in zip(reversed(left_parts), reversed(right_parts)):
        if left_part != right_part:
            break
        shared += 1
    return shared == min(len(left_parts), len(right_parts)) or shared >= 2
