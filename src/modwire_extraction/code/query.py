from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Generic, TypeVar

from ..extractors.source import SourceFile
from .code_map import CodeMap


T = TypeVar("T")


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


class QueryableCodeMap:
    def __init__(self, code_map: CodeMap):
        self.code_map = code_map
        self.cm = code_map

    def query(self, items: Iterable[T]) -> QueryBuilder[T]:
        return QueryBuilder(items)

    def source_files(self) -> QueryBuilder[SourceFileResult]:
        return QueryBuilder(
            SourceFileResult(source_id=source_id, file=source_file)
            for source_id, source_file in self.code_map.extraction.files.items()
        )
