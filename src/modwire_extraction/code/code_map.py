from dataclasses import dataclass


@dataclass(frozen=True)
class CodeMap:
    language: str
    extraction: SourceExtraction
    dependency_graph: DependencyGraph
