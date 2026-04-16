from __future__ import annotations

from pathlib import Path


def load_prompt_file(path: Path, fallback: str) -> str:
    try:
        if not path.exists() or not path.is_file():
            return fallback
        content = path.read_text(encoding="utf-8").strip()
        return content if content else fallback
    except OSError:
        return fallback
