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


def test_queryable_code_map_exposes_report_query_surfaces() -> None:
    queryable_map = ModwireExtraction(FIXTURE_ROOT / "python").generate_queryable_map(
        "python"
    )

    assert queryable_map.source_ids() == (
        "src/application/use_cases/activate",
        "src/domain/model/user",
        "src/domain/services/policy",
        "src/interfaces/http/controller",
    )
    assert queryable_map.has_source_file("src/interfaces/http/controller")
    assert queryable_map.files().count() == queryable_map.source_files().count()

    controller = queryable_map.source_file("src/interfaces/http/controller")
    assert controller is not None
    assert controller.file.classes[0].name == "ActivationController"

    controller_class = (
        queryable_map.classes()
        .where_equal(lambda result: result.item.name, "ActivationController")
        .first()
    )
    assert controller_class is not None
    assert controller_class.source_id == "src/interfaces/http/controller"

    activation_label = (
        queryable_map.functions()
        .where_equal(lambda result: result.item.name, "activation_label")
        .first()
    )
    assert activation_label is not None
    assert activation_label.source_id == "src/application/use_cases/activate"

    domain_model_imports = queryable_map.imports().where_equal(
        lambda result: result.item.normalized_path,
        "domain/model/user",
    )
    assert domain_model_imports.count() == 3
    assert queryable_map.exports().count() == 8

    policy_method = (
        queryable_map.callables()
        .where_equal(lambda result: result.item.qualified_name, "ActivationPolicy.allows")
        .first()
    )
    assert policy_method is not None
    assert policy_method.source_id == "src/domain/services/policy"

    resolved_call = (
        queryable_map.calls()
        .where_equal(lambda result: result.item.resolution, "resolved")
        .first()
    )
    assert resolved_call is not None
    assert (
        resolved_call.item.target_callable_id
        == "src/domain/services/policy::can_activate"
    )

    controller_activation_edges = queryable_map.dependencies_between(
        "src/interfaces/http/controller",
        "application/use_cases/activate",
    )
    assert controller_activation_edges.count() == 2
    assert (
        queryable_map.outgoing_dependencies("src/interfaces/http/controller").count()
        == 4
    )
    assert queryable_map.incoming_dependencies("domain/model/user").count() == 3
    assert queryable_map.dependency_edges().count() == 10
    assert queryable_map.tracked_dependency_edges().count() == 0
    assert queryable_map.external_dependency_edges().count() == 10

    source_node = (
        queryable_map.dependency_nodes()
        .where_equal(lambda result: result.node_id, "src/interfaces/http/controller")
        .first()
    )
    assert source_node is not None
    assert source_node.file == controller.file

    external_node = (
        queryable_map.dependency_nodes()
        .where_equal(lambda result: result.node_id, "json")
        .first()
    )
    assert external_node is not None
    assert external_node.file is None


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
