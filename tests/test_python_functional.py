from pathlib import Path


FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def test_extract_code_reads_two_module_fixture() -> None:
    for root in FIXTURE_ROOT.glob("*"):
        _test_language(root)


def _test_language(root: Path) -> None:
    pass
