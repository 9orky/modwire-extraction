from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Generic, TypeVar

from ..dependency.graph import Edge, Node
from ..extractors.source import (
    SourceAbstractClass,
    SourceCall,
    SourceCallable,
    SourceClass,
    SourceExport,
    SourceFile,
    SourceFunction,
    SourceImport,
    SourceInterface,
    SourceType,
    SourceValue,
)
from .code_map import CodeMap


T = TypeVar("T")
SourceItem = TypeVar("SourceItem")


class QueryBuilder(Generic[T]):
    def __init__(
        self,
        items: Iterable[T],
        predicates: tuple[Callable[[T], bool], ...] = (),
    ):
        self._items = tuple(items)
        self._predicates = predicates

    def where(self, predicate: Callable[[T], bool]) -> QueryBuilder[T]:
        return QueryBuilder(self._items, (*self._predicates, predicate))

    def where_equal(
        self,
        selector: Callable[[T], object],
        expected: object,
    ) -> QueryBuilder[T]:
        return self.where(lambda item: selector(item) == expected)

    def where_contains(
        self,
        selector: Callable[[T], str],
        expected: str,
        *,
        case_sensitive: bool = True,
    ) -> QueryBuilder[T]:
        if case_sensitive:
            return self.where(lambda item: expected in selector(item))

        lowered = expected.casefold()
        return self.where(lambda item: lowered in selector(item).casefold())

    def all(self) -> tuple[T, ...]:
        return tuple(
            item
            for item in self._items
            if all(predicate(item) for predicate in self._predicates)
        )

    def first(self) -> T | None:
        for item in self.all():
            return item
        return None

    def count(self) -> int:
        return len(self.all())


@dataclass(frozen=True)
class SourceFileResult:
    source_id: str
    file: SourceFile


@dataclass(frozen=True)
class SourceItemResult(Generic[SourceItem]):
    source_id: str
    file: SourceFile
    item: SourceItem


@dataclass(frozen=True)
class DependencyNodeResult:
    node_id: str
    node: Node
    file: SourceFile | None


@dataclass(frozen=True)
class DependencyEdgeResult:
    edge: Edge
    source_file: SourceFile | None
    target_file: SourceFile | None


class QueryableCodeMap:
    def __init__(self, code_map: CodeMap):
        self.code_map = code_map
        self.cm = code_map

    def query(self, items: Iterable[T]) -> QueryBuilder[T]:
        return QueryBuilder(items)

    def source_ids(self) -> tuple[str, ...]:
        return tuple(self.code_map.extraction.files)

    def has_source_file(self, source_id: str) -> bool:
        return source_id in self.code_map.extraction.files

    def source_file(self, source_id: str) -> SourceFileResult | None:
        source_file = self.code_map.extraction.files.get(source_id)
        if source_file is None:
            return None
        return SourceFileResult(source_id=source_id, file=source_file)

    def files(self) -> QueryBuilder[SourceFileResult]:
        return self.source_files()

    def source_files(self) -> QueryBuilder[SourceFileResult]:
        return QueryBuilder(
            SourceFileResult(source_id=source_id, file=source_file)
            for source_id, source_file in self.code_map.extraction.files.items()
        )

    def imports(self) -> QueryBuilder[SourceItemResult[SourceImport]]:
        return self._source_items(lambda source_file: source_file.imports)

    def exports(self) -> QueryBuilder[SourceItemResult[SourceExport]]:
        return self._source_items(lambda source_file: source_file.exports)

    def classes(self) -> QueryBuilder[SourceItemResult[SourceClass]]:
        return self._source_items(lambda source_file: source_file.classes)

    def interfaces(self) -> QueryBuilder[SourceItemResult[SourceInterface]]:
        return self._source_items(lambda source_file: source_file.interfaces)

    def types(self) -> QueryBuilder[SourceItemResult[SourceType]]:
        return self._source_items(lambda source_file: source_file.types)

    def abstract_classes(self) -> QueryBuilder[SourceItemResult[SourceAbstractClass]]:
        return self._source_items(lambda source_file: source_file.abstract_classes)

    def functions(self) -> QueryBuilder[SourceItemResult[SourceFunction]]:
        return self._source_items(lambda source_file: source_file.functions)

    def values(self) -> QueryBuilder[SourceItemResult[SourceValue]]:
        return self._source_items(lambda source_file: source_file.values)

    def callables(self) -> QueryBuilder[SourceItemResult[SourceCallable]]:
        return self._source_items(lambda source_file: source_file.callables)

    def calls(self) -> QueryBuilder[SourceItemResult[SourceCall]]:
        return self._source_items(lambda source_file: source_file.calls)

    def dependency_nodes(self) -> QueryBuilder[DependencyNodeResult]:
        files = self.code_map.extraction.files
        return QueryBuilder(
            DependencyNodeResult(
                node_id=node_id,
                node=node,
                file=files.get(node_id),
            )
            for node_id, node in self.code_map.dependency_graph.nodes.items()
        )

    def dependency_edges(self) -> QueryBuilder[DependencyEdgeResult]:
        return self._dependency_edges(self.code_map.dependency_graph.edges)

    def outgoing_dependencies(self, source_id: str) -> QueryBuilder[DependencyEdgeResult]:
        return self._dependency_edges(self.code_map.dependency_graph.outgoing(source_id))

    def incoming_dependencies(self, source_id: str) -> QueryBuilder[DependencyEdgeResult]:
        return self._dependency_edges(self.code_map.dependency_graph.incoming(source_id))

    def dependencies_between(
        self,
        source_id: str,
        target_id: str,
    ) -> QueryBuilder[DependencyEdgeResult]:
        return self._dependency_edges(
            self.code_map.dependency_graph.edges_between(source_id, target_id)
        )

    def tracked_dependency_edges(self) -> QueryBuilder[DependencyEdgeResult]:
        return self._dependency_edges(
            self.code_map.dependency_graph.tracked_edges(self.source_ids())
        )

    def external_dependency_edges(self) -> QueryBuilder[DependencyEdgeResult]:
        return self._dependency_edges(
            self.code_map.dependency_graph.external_edges(self.source_ids())
        )

    def _source_items(
        self,
        selector: Callable[[SourceFile], Iterable[SourceItem]],
    ) -> QueryBuilder[SourceItemResult[SourceItem]]:
        return QueryBuilder(
            SourceItemResult(source_id=source_id, file=source_file, item=item)
            for source_id, source_file in self.code_map.extraction.files.items()
            for item in selector(source_file)
        )

    def _dependency_edges(
        self,
        edges: Iterable[Edge],
    ) -> QueryBuilder[DependencyEdgeResult]:
        files = self.code_map.extraction.files
        return QueryBuilder(
            DependencyEdgeResult(
                edge=edge,
                source_file=files.get(edge.from_id),
                target_file=files.get(edge.to_id),
            )
            for edge in edges
        )
