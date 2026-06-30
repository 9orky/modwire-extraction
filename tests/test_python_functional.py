import shutil
from pathlib import Path

import pytest

from modwire_extraction import ModwireExtraction
from modwire_extraction.code import CodeMap
from modwire_extraction.extractors.source import SourceFile


FIXTURE_ROOT = Path(__file__).parent / "fixtures"

REQUIRED_RUNTIME = {
    "php": "php",
    "python": None,
    "typescript": "node",
}

SOURCE_FILE_SHAPE = set(SourceFile.model_fields)


def _language_roots() -> list[Path]:
    return sorted(path for path in FIXTURE_ROOT.iterdir() if path.is_dir())


def _skip_missing_runtime(language: str) -> None:
    runtime = REQUIRED_RUNTIME[language]
    if runtime is not None and shutil.which(runtime) is None:
        pytest.skip(f"{runtime} is required for {language} extraction")


@pytest.mark.parametrize("root", _language_roots(), ids=lambda path: path.name)
def test_public_api_reads_each_language_project_with_same_shape(root: Path) -> None:
    language = root.name
    _skip_missing_runtime(language)

    extraction = ModwireExtraction(root)
    assert extraction.discover() == (language,)

    queryable_map = extraction.generate_queryable_map(language)
    code_map = queryable_map.code_map
    files_dict = code_map.extraction.files_dict()

    assert queryable_map.cm is code_map
    assert code_map.language == language
    assert set(files_dict) == set(code_map.extraction.files)
    assert code_map.extraction.files_found == len(code_map.extraction.files)
    assert code_map.extraction.files_excluded == 1
    assert all(
        set(type(source_file).model_fields) == SOURCE_FILE_SHAPE
        for source_file in files_dict.values()
    )

    controller = (
        queryable_map.source_files()
        .where_contains(lambda result: result.source_id, "interfaces/http/controller")
        .first()
    )

    assert controller is not None
    assert controller.source_id in files_dict
    assert controller.file == files_dict[controller.source_id]

    source_files = (
        queryable_map.source_files()
        .where(lambda result: result.source_id.startswith("src/"))
        .all()
    )

    assert len(source_files) == code_map.extraction.files_found
    assert (
        queryable_map.query(files_dict.items()).where(_has_public_symbols).count()
        >= 1
    )


@pytest.mark.parametrize("root", _language_roots(), ids=lambda path: path.name)
def test_code_map_serialization_round_trips_through_pydantic(root: Path) -> None:
    language = root.name
    _skip_missing_runtime(language)

    original = ModwireExtraction(root).generate_map(language)
    payload = original.model_dump(mode="python")

    assert set(payload) == {"language", "extraction", "dependency_graph"}
    assert set(payload["dependency_graph"]) == {"nodes", "edges"}

    restored = CodeMap.model_validate(payload)
    json_restored = CodeMap.model_validate_json(original.model_dump_json())

    assert restored.model_dump(mode="python") == payload
    assert json_restored.model_dump(mode="python") == payload
    assert restored.dependency_graph.node_ids() == original.dependency_graph.node_ids()


def _has_public_symbols(item: tuple[str, SourceFile]) -> bool:
    return item[1].public_symbol_count > 0
