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
    
    return _instances[language]
