from dataclasses import dataclass
from pathlib import Path

from .dependency import build_dependency_graph
from .dependency.graph import DependencyGraph
from .extractors import languages
from .extractors.languages.base import SourceExtraction


@dataclass(frozen=True)
class CodeMap:
    language: str
    extraction: SourceExtraction
    dependency_graph: DependencyGraph


class ModwireCodeMap:
    def __init__(self, root: Path):
        self._root = root.resolve()

    def discover(self) -> tuple[str, ...]:
        discovered: list[str] = []
        for language in languages.get_supported_languages():
            extractor = languages.load_extractor(language)
            extensions = extractor.runtime.file_extensions
            if any(
                path.is_file() and path.suffix.lower() in extensions
                for path in self._root.rglob("*")
            ):
                discovered.append(language)
        return tuple(discovered)

    def generate_map(self, language: str) -> CodeMap:
        available = languages.get_supported_languages()
        if language not in available:
            raise ValueError(f"Language is not supported: {language}")

        extraction = languages.load_extractor(language).extract_source(self._root)
        dependency_graph = build_dependency_graph(extraction.files)
        return CodeMap(
            language=language,
            extraction=extraction,
            dependency_graph=dependency_graph,
        )
