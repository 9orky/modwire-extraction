from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from ..extractors.source import SourceFile
from ..identity import FileId, ImportSpecifier

EdgeResolution = Literal["resolved", "unresolved", "external"]


class Node(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: FileId
    kind: str = "file"


class Edge(BaseModel):
    model_config = ConfigDict(frozen=True)

    from_id: FileId
    to_id: FileId | None
    specifier: ImportSpecifier
    resolution: EdgeResolution
    kind: str = "import"


def _empty_edges() -> list[Edge]:
    return []


def _empty_nodes() -> dict[FileId, Node]:
    return {}


def _empty_edge_index() -> dict[FileId, list[Edge]]:
    return {}


class DependencyGraph(BaseModel):
    nodes: dict[FileId, Node] = Field(default_factory=_empty_nodes)
    edges: list[Edge] = Field(default_factory=_empty_edges)
    _outgoing_by_node: dict[FileId, list[Edge]] = PrivateAttr(
        default_factory=_empty_edge_index
    )
    _incoming_by_node: dict[FileId, list[Edge]] = PrivateAttr(
        default_factory=_empty_edge_index
    )

    def model_post_init(self, __context: Any) -> None:
        self._rebuild_indexes()

    def _rebuild_indexes(self) -> None:
        self._outgoing_by_node = {node_id: [] for node_id in self.nodes}
        self._incoming_by_node = {node_id: [] for node_id in self.nodes}
        for edge in self.edges:
            self._outgoing_by_node.setdefault(edge.from_id, []).append(edge)
            if edge.to_id is not None:
                self._incoming_by_node.setdefault(edge.to_id, []).append(edge)

    def add_node(self, node_id: FileId, *, kind: str = "file") -> None:
        self.nodes.setdefault(node_id, Node(id=node_id, kind=kind))
        self._outgoing_by_node.setdefault(node_id, [])
        self._incoming_by_node.setdefault(node_id, [])

    def add_edge(
        self,
        from_id: FileId,
        to_id: FileId | None,
        *,
        specifier: ImportSpecifier,
        resolution: EdgeResolution,
        kind: str = "import",
    ) -> None:
        self.add_node(from_id)
        if to_id is not None:
            self.add_node(to_id)
        edge = Edge(
            from_id=from_id,
            to_id=to_id,
            specifier=specifier,
            resolution=resolution,
            kind=kind,
        )
        self.edges.append(edge)
        self._outgoing_by_node[from_id].append(edge)
        if to_id is not None:
            self._incoming_by_node[to_id].append(edge)

    def outgoing(self, node_id: FileId) -> tuple[Edge, ...]:
        return tuple(self._outgoing_by_node.get(node_id, ()))

    def incoming(self, node_id: FileId) -> tuple[Edge, ...]:
        return tuple(self._incoming_by_node.get(node_id, ()))

    def edges_between(self, source: FileId, target: FileId) -> tuple[Edge, ...]:
        return tuple(
            edge
            for edge in self._outgoing_by_node.get(source, ())
            if edge.to_id == target
        )

    def has_node(self, node_id: FileId) -> bool:
        return node_id in self.nodes

    def node_ids(self) -> tuple[FileId, ...]:
        return tuple(self.nodes.keys())

    def sorted_nodes(self) -> tuple[Node, ...]:
        return tuple(self.nodes[node_id] for node_id in sorted(self.nodes))

    def sorted_edges(self) -> tuple[Edge, ...]:
        return tuple(
            sorted(
                self.edges,
                key=lambda edge: (edge.from_id, edge.to_id, edge.kind),
            )
        )

    def subgraph(
        self,
        node_ids: set[FileId] | tuple[FileId, ...],
    ) -> DependencyGraph:
        selected = set(node_ids)
        graph = DependencyGraph()
        for node_id in sorted(selected):
            if node_id in self.nodes:
                graph.add_node(node_id, kind=self.nodes[node_id].kind)
        for edge in self.edges:
            if edge.from_id in selected and edge.to_id in selected:
                graph.add_edge(
                    edge.from_id,
                    edge.to_id,
                    specifier=edge.specifier,
                    resolution=edge.resolution,
                    kind=edge.kind,
                )
        return graph

    def without_external_nodes(
        self,
        tracked_ids: set[FileId] | tuple[FileId, ...],
    ) -> DependencyGraph:
        return self.subgraph(set(tracked_ids))

    def tracked_edges(
        self,
        tracked_ids: set[FileId] | tuple[FileId, ...],
    ) -> tuple[Edge, ...]:
        tracked = set(tracked_ids)
        return tuple(edge for edge in self.edges if edge.to_id in tracked)

    def external_edges(
        self,
        tracked_ids: set[FileId] | tuple[FileId, ...],
    ) -> tuple[Edge, ...]:
        tracked = set(tracked_ids)
        return tuple(edge for edge in self.edges if edge.to_id not in tracked)


def build_dependency_graph(
    extracted_files: dict[FileId, SourceFile],
) -> DependencyGraph:
    graph = DependencyGraph()

    for file_path, extracted_file in extracted_files.items():
        graph.add_node(file_path)
        for imported_reference in extracted_file.imports:
            graph.add_edge(
                file_path,
                imported_reference.target_file_id,
                specifier=imported_reference.normalized_path,
                resolution=imported_reference.resolution,
            )

    return graph
