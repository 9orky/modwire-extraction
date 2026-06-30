from pathlib import Path

from modwire_extraction.code_map import extract_code


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "python" / "src"


def test_extract_code_reads_two_module_fixture() -> None:
    code_map = extract_code("python", FIXTURE_ROOT)

    assert code_map.source_ids() == (
        "application/use_cases/activate",
        "domain/model/user",
        "domain/services/policy",
        "interfaces/http/controller",
    )
    assert code_map.extraction_result.summary.files_found == 4
    assert code_map.extraction_result.summary.files_checked == 4
    assert code_map.cache_status == "disabled"


def test_extract_code_tracks_fixture_import_and_callables() -> None:
    code_map = extract_code("python", FIXTURE_ROOT)

    controller_file = code_map.extraction_result.files["interfaces/http/controller"]
    import_paths = {
        source_import.normalized_path for source_import in controller_file.imports
    }
    callable_ids = set(code_map.callable_ids())

    assert "application/use_cases/activate" in import_paths
    assert "domain/model/user" in import_paths
    assert "interfaces/http/controller::ActivationController.handle" in callable_ids
    assert "application/use_cases/activate::build_activation_command" in callable_ids
