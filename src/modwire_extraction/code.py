from .extractors import languages


class ModwireCodeMap:
    def __init__(self, root: Path):
        self._root = root

    def discover(self):
        pass

    def generate_map(self, language: str):
        available = languages.get_supported_languages()
        assert language in available, f"Language: {language} is not supported"

        extractor = languages.load_extractor(language).extract_source()