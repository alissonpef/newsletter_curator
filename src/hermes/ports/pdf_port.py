from pathlib import Path
from typing import Any, Protocol


class PdfPort(Protocol):
    def render(self, template_name: str, context: dict[str, Any], output_path: Path) -> Path: ...
