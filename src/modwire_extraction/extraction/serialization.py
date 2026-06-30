from __future__ import annotations

from typing import Any

from ..definitions import SourceFile
from ..graph import DependencyGraph, Edge, Node
from .models import CodeMap, ExtractionResult, ExtractionSummary


CODE_MAP_SCHEMA_VERSION = 2
SUPPORTED_CODE_MAP_SCHEMA_VERSIONS = {1, CODE_MAP_SCHEMA_VERSION}


class CodeMapSerializationError(ValueError):
    """Raised when serialized CodeMap payloads cannot be loaded."""


def serialize_code_map(code_map: CodeMap) -> dict[str, Any]:
    return {
        "schema_version": CODE_MAP_SCHEMA_VERSION,
        "runtime_command": code_map.runtime_command,
        "cache_status": code_map.cache_status,
        "cache_key": code_map.cache_key,
        "extraction_result": {
            "summary": {
                "files_found": code_map.extraction_result.summary.files_found,
                "files_checked": code_map.extraction_result.summary.files_checked,
                "files_excluded": code_map.extraction_result.summary.files_excluded,
            },
            "files": {
                source_id: source_file.model_dump(mode="json")
                for source_id, source_file in code_map.extraction_result.files.items()
            },
        },
        "graph": {
            "nodes": {
                node_id: {"id": node.id, "kind": node.kind}
                for node_id, node in code_map.graph.nodes.items()
            },
            "edges": [
                {
                    "from_id": edge.from_id,
                    "to_id": edge.to_id,
                    "kind": edge.kind,
                }
                for edge in code_map.graph.edges
            ],
        },
    }


def deserialize_code_map(
    payload: dict[str, Any],
    *,
    cache_status: str = "",
    cache_key: str = "",
) -> CodeMap:
    try:
        if payload["schema_version"] not in SUPPORTED_CODE_MAP_SCHEMA_VERSIONS:
            raise CodeMapSerializationError(
                f"Unsupported CodeMap schema version: {payload['schema_version']}"
            )

        summary_payload = payload["extraction_result"]["summary"]
        files_payload = payload["extraction_result"]["files"]
        graph_payload = payload["graph"]

        graph = DependencyGraph()
        graph.nodes = {
            node_id: Node(id=node_payload["id"], kind=node_payload["kind"])
            for node_id, node_payload in graph_payload["nodes"].items()
        }
        graph.edges = [
            Edge(
                from_id=edge_payload["from_id"],
                to_id=edge_payload["to_id"],
                kind=edge_payload["kind"],
            )
            for edge_payload in graph_payload["edges"]
        ]
        graph._outgoing_by_node = {node_id: [] for node_id in graph.nodes}
        graph._incoming_by_node = {node_id: [] for node_id in graph.nodes}
        for edge in graph.edges:
            graph._outgoing_by_node.setdefault(edge.from_id, []).append(edge)
            graph._incoming_by_node.setdefault(edge.to_id, []).append(edge)

        return CodeMap(
            graph=graph,
            extraction_result=ExtractionResult(
                files={
                    source_id: SourceFile.model_validate(source_file_payload)
                    for source_id, source_file_payload in files_payload.items()
                },
                summary=ExtractionSummary(
                    files_found=summary_payload["files_found"],
                    files_checked=summary_payload["files_checked"],
                    files_excluded=summary_payload["files_excluded"],
                ),
            ),
            runtime_command=payload["runtime_command"],
            cache_status=cache_status or payload.get("cache_status", "disabled"),
            cache_key=cache_key or payload.get("cache_key") or "",
        )
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, CodeMapSerializationError):
            raise
        raise CodeMapSerializationError("Invalid serialized CodeMap payload") from error
