from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from ..dependency.graph import DependencyGraph
from ..extractors.languages.base import SourceExtraction


class CodeMap(BaseModel):
    model_config = ConfigDict(frozen=True)

    language: str
    extraction: SourceExtraction
    dependency_graph: DependencyGraph

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="python")

    @classmethod
    def from_dict(cls, payload: object) -> CodeMap:
        return cls.model_validate(payload)

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, payload: str | bytes) -> CodeMap:
        return cls.model_validate_json(payload)
