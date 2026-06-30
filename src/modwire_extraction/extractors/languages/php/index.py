from dataclasses import dataclass

@dataclass(frozen=True)
class PhpSourceIndex:
    known_source_ids: set[str]
    unique_suffixes: dict[str, str | None]
    namespace_suffixes: dict[str, str | None]

    def build(self, known_source_ids: set[str]) -> PhpSourceIndex:
        unique_suffixes: dict[str, str | None] = {}
        namespace_suffixes: dict[str, str | None] = {}
        for source_id in known_source_ids:
            self._add_unique_suffixes(unique_suffixes, source_id.split("/"), source_id)
            parent = PhpExtractor._source_parent(source_id)
            if parent != ".":
                self._add_unique_suffixes(namespace_suffixes, parent.split("/"), source_id)
        return PhpSourceIndex(
            known_source_ids=known_source_ids,
            unique_suffixes=unique_suffixes,
            namespace_suffixes=namespace_suffixes,
        )

    def _add_unique_suffixes(
        self,
        suffixes: dict[str, str | None],
        parts: list[str],
        source_id: str,
    ) -> None:
        for index in range(len(parts)):
            suffix = "/".join(parts[index:])
            previous = suffixes.get(suffix)
            if previous is None and suffix in suffixes:
                continue
            if previous is not None and previous != source_id:
                suffixes[suffix] = None
                continue
            suffixes[suffix] = source_id