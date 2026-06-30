from .code_map import CodeMap


class QueryableCodeMap:
    def __init__(self, code_map: CodeMap):
        self.cm = code_map

    