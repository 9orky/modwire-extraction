from __future__ import annotations

from pathlib import Path

from ..extractors import load_extractor
from ..graph import build_dependency_graph
from .cache import DEFAULT_EXTRACTION_CACHE, ExtractionCache
from .manifest import discover_sources
from .models import CodeMap, ExtractionResult, ExtractionSummary
from .roots import (
    DEFAULT_SOURCE_ROOTS,
    SourceRoots,
    normalize_exclusions,
    source_id_prefix,
)


class SourceChangedDuringExtractionError(RuntimeError):
    """Raised when source files change while extraction is running."""


def extract_code(
    language: str,
    sources_root: Path,
    exclusions: tuple[str, ...] = (),
    *,
    source_roots: SourceRoots = DEFAULT_SOURCE_ROOTS,
    cache: ExtractionCache = DEFAULT_EXTRACTION_CACHE,
) -> CodeMap:
    """Extract code from the source root and build a dependency graph."""
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
    cache_enabled = cache.enabled
    manifest = None
    cache_key = None

    if cache_enabled:
        manifest = discover_sources(
            language,
            sources_root,
            exclusions,
            source_roots=source_roots,
        )
        cache_key = manifest.fingerprint()
        cached_code_map = cache.load(cache_key)
        if cached_code_map is not None:
            return cached_code_map

    extraction = extractor.extract_files(
        sources_root,
        normalized_exclusions,
        source_id_prefix=prefix,
    )
    if cache_enabled:
        post_extraction_manifest = discover_sources(
            language,
            sources_root,
            exclusions,
            source_roots=source_roots,
        )
        if post_extraction_manifest.fingerprint() != cache_key:
            raise SourceChangedDuringExtractionError(
                "Source files changed during extraction; retry with a stable tree."
            )

    extracted_files = extraction.files
    dependency_graph = build_dependency_graph(extracted_files)

    extraction_result = ExtractionResult(
        files=extracted_files,
        summary=ExtractionSummary(
            files_found=extraction.files_found,
            files_checked=len(extracted_files),
            files_excluded=extraction.files_excluded,
        ),
    )

    code_map = CodeMap(
        graph=dependency_graph,
        extraction_result=extraction_result,
        runtime_command=extractor.command,
        cache_status="miss" if cache_enabled else "disabled",
        cache_key=cache_key if cache_enabled else "",
    )
    if cache_enabled:
        assert manifest is not None
        assert cache_key is not None
        cache.store(cache_key, code_map, manifest)

    return code_map
