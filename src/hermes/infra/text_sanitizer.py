from __future__ import annotations

import html
import re
from typing import Literal


SanitizeProfile = Literal["fallback", "tts", "summary"]


class TextSanitizer:
    _NOISE_PATTERNS = (
        r"\bver imagem:?\b",
        r"\bcaption:?\b",
        r"\bleia o conte[úu]do deste e-?mail no seu browser\b",
        r"\bclique aqui\b",
        r"\bunsubscribe\b",
        r"\bsaiba mais\b",
        r"\bgood morning\b",
        r"\bnewsletter\b",
    )

    def sanitize(self, text: str, profile: SanitizeProfile = "fallback") -> str:
        sanitized = html.unescape(text or "")
        sanitized = sanitized.replace("\r\n", "\n").replace("\r", "\n")
        sanitized = re.sub(r"https?://\S+", " ", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(
            r"\b(?:utm_[a-z_]+|view in browser|leia no navegador|unsubscribe)\b",
            " ",
            sanitized,
            flags=re.IGNORECASE,
        )

        if profile in {"fallback", "summary"}:
            for pattern in self._NOISE_PATTERNS:
                sanitized = re.sub(pattern, " ", sanitized, flags=re.IGNORECASE)
            sanitized = re.sub(r"(?:\s*[:;,\-()\[\]{}]\s*){3,}", " ", sanitized)
            sanitized = re.sub(r"\([^)]{0,120}\)", " ", sanitized)

        if profile == "tts":
            sanitized = " ".join(line.strip(" -\t") for line in sanitized.split("\n") if line.strip())

        sanitized = re.sub(r"[_=*~]{2,}", " ", sanitized)
        sanitized = re.sub(r"[^\w\s.,;:!?%()\-/\$]", " ", sanitized, flags=re.UNICODE)
        sanitized = re.sub(r"\s+", " ", sanitized).strip()
        return sanitized
