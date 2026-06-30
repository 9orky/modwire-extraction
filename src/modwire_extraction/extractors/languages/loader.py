import shutil

from .base import SourceExtractor

from .php.source import PhpExtractor
from .python.source import PythonExtractor
from .typescript.source import TypeScriptExtractor


_map: dict[str, type[SourceExtractor]] = {
    "python": PythonExtractor,
    "typescript": TypeScriptExtractor,
    "php": PhpExtractor,
}

_instances: dict[str, SourceExtractor] = {}


def get_supported_languages() -> tuple[str, ...]:
    return tuple(_map)


def load_extractor(language: str) -> SourceExtractor:
    if language not in _map:
        raise ValueError(f"Unsupported language: {language}")

    if language not in _instances:
        _instances[language] = _map[language]()

    extractor = _instances[language]
    _ensure_runtime_command_available(extractor)
    return extractor


def _ensure_runtime_command_available(extractor: SourceExtractor) -> None:
    runtime = extractor.runtime
    executable = runtime.command[0]
    if shutil.which(executable) is None:
        raise RuntimeError(
            f"{runtime.language} extractor runtime is not available on PATH: "
            f"{executable}"
        )
