from __future__ import annotations

import sys

from ..base import (
    SourceExtractor,
)


class PythonExtractor(SourceExtractor):
    language = "python"
    file_extensions = (".py",)
    command = sys.executable
