from pathlib import Path

from modwire_extraction.extraction import extract_code


FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def test_extract_code_reads_two_module_fixture() -> None:
    code_map = extract_code("python", FIXTURE_ROOT)

    assert code_map.source_ids() == ("app", "helpers")
    assert code_map.extraction_result.summary.files_found == 2
    assert code_map.extraction_result.summary.files_checked == 2
    assert code_map.cache_status == "disabled"


def test_extract_code_tracks_fixture_import_and_callables() -> None:
    code_map = extract_code("python", FIXTURE_ROOT)

    app_file = code_map.extraction_result.files["app"]
    import_paths = {source_import.normalized_path for source_import in app_file.imports}
    callable_ids = set(code_map.callable_ids())

    assert "helpers" in import_paths
    assert "app::Greeter.greet" in callable_ids
    assert "app::build_message" in callable_ids
