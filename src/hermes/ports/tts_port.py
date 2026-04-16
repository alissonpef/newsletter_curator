from pathlib import Path
from typing import Protocol


class TtsPort(Protocol):
    def synthesize(self, script_text: str, output_path: Path) -> Path: ...
