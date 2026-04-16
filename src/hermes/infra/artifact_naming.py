from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path


class ArtifactNamingService:
    def __init__(self, max_slug_length: int = 48) -> None:
        self._max_slug_length = max(16, int(max_slug_length))

    def slugify(self, value: str, default: str = "digest") -> str:
        normalized = unicodedata.normalize("NFKD", value)
        ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()
        return slug[: self._max_slug_length].strip("-") or default

    def build_versioned_path(
        self,
        *,
        output_dir: Path,
        date_ref: date,
        hint: str,
        extension: str,
        stem_prefix: str = "",
        default_hint: str = "newsletter",
    ) -> Path:
        slug = self.slugify(hint, default=default_hint)
        prefix = stem_prefix.strip("-")
        stem_parts = [date_ref.isoformat()]
        if prefix:
            stem_parts.append(prefix)
        stem_parts.append(slug)
        stem = "-".join(stem_parts)

        ext = extension if extension.startswith(".") else f".{extension}"
        candidate = output_dir / f"{stem}{ext}"
        if not candidate.exists():
            return candidate

        version = 2
        while True:
            candidate = output_dir / f"{stem}-v{version}{ext}"
            if not candidate.exists():
                return candidate
            version += 1
