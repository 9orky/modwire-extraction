from __future__ import annotations

from dataclasses import dataclass, field

from ..extractors.source import SourceFile


@dataclass(frozen=True)
class Node:
    id: str
    kind: str = "file"


@dataclass(frozen=True)
class Edge:
    from_id: str
    to_id: str
    kind: str = "import"


@dataclass
class DependencyGraph:
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    _outgoing_by_node: dict[str, list[Edge]] = field(default_factory=dict)
    _incoming_by_node: dict[str, list[Edge]] = field(default_factory=dict)

    def add_node(self, node_id: str, *, kind: str = "file") -> None:
        self.nodes.setdefault(node_id, Node(id=node_id, kind=kind))
        self._outgoing_by_node.setdefault(node_id, [])
        self._incoming_by_node.setdefault(node_id, [])

    def add_edge(self, from_id: str, to_id: str, *, kind: str = "import") -> None:
        self.add_node(from_id)
        self.add_node(to_id)
        edge = Edge(from_id=from_id, to_id=to_id, kind=kind)
        self.edges.append(edge)
        self._outgoing_by_node[from_id].append(edge)
        self._incoming_by_node[to_id].append(edge)

    def outgoing(self, node_id: str) -> tuple[Edge, ...]:
        return tuple(self._outgoing_by_node.get(node_id, ()))

    def incoming(self, node_id: str) -> tuple[Edge, ...]:
        return tuple(self._incoming_by_node.get(node_id, ()))

    def edges_between(self, source: str, target: str) -> tuple[Edge, ...]:
        return tuple(
            edge
            for edge in self._outgoing_by_node.get(source, ())
            if edge.to_id == target
        )

    def has_node(self, node_id: str) -> bool:
        return node_id in self.nodes

    def node_ids(self) -> tuple[str, ...]:
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

    def subgraph(self, node_ids: set[str] | tuple[str, ...]) -> DependencyGraph:
        selected = set(node_ids)
        graph = DependencyGraph()
        for node_id in sorted(selected):
            if node_id in self.nodes:
                graph.add_node(node_id, kind=self.nodes[node_id].kind)
        for edge in self.edges:
            if edge.from_id in selected and edge.to_id in selected:
                graph.add_edge(edge.from_id, edge.to_id, kind=edge.kind)
        return graph

    def without_external_nodes(
        self,
        tracked_ids: set[str] | tuple[str, ...],
    ) -> DependencyGraph:
        return self.subgraph(set(tracked_ids))

    def tracked_edges(self, tracked_ids: set[str] | tuple[str, ...]) -> tuple[Edge, ...]:
        tracked = set(tracked_ids)
        return tuple(
            edge
            for edge in self.edges
            if edge.from_id in tracked and edge.to_id in tracked
        )

    def external_edges(self, tracked_ids: set[str] | tuple[str, ...]) -> tuple[Edge, ...]:
        tracked = set(tracked_ids)
        return tuple(
            edge
            for edge in self.edges
            if edge.from_id not in tracked or edge.to_id not in tracked
        )


def build_dependency_graph(extracted_files: dict[str, SourceFile]) -> DependencyGraph:
    graph = DependencyGraph()

    for file_path, extracted_file in extracted_files.items():
        graph.add_node(file_path)
        for imported_reference in extracted_file.imports:
            graph.add_edge(file_path, imported_reference.normalized_path)

    return graph
