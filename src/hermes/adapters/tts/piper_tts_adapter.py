from __future__ import annotations

import subprocess
import wave
from pathlib import Path

from ...core.errors import TtsSynthesisError


class PiperTtsAdapter:
    def __init__(self, piper_executable: str, model_path: Path, sample_rate: int) -> None:
        self._piper_executable = piper_executable
        self._model_path = model_path
        if int(sample_rate) <= 0:
            raise ValueError("sample_rate must be positive")
        self._sample_rate = int(sample_rate)

    def synthesize(self, script_text: str, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        normalized_text = " ".join(part.strip() for part in script_text.splitlines() if part.strip())
        if not normalized_text:
            raise TtsSynthesisError("piper synthesis failed: empty script text")

        command = [
            self._piper_executable,
            "--model",
            str(self._model_path),
            "--output_file",
            str(output_path),
        ]

        completed = subprocess.run(
            command,
            input=normalized_text.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="ignore")
            raise TtsSynthesisError(f"piper synthesis failed: {stderr}")

        if not output_path.exists():
            raise TtsSynthesisError("piper did not produce output audio file")

        self._validate_output_sample_rate(output_path)

        return output_path

    def _validate_output_sample_rate(self, output_path: Path) -> None:
        try:
            with wave.open(str(output_path), "rb") as stream:
                rendered_sample_rate = int(stream.getframerate())
        except (wave.Error, OSError):
            return

        if rendered_sample_rate != self._sample_rate:
            raise TtsSynthesisError(
                "piper output sample rate mismatch: "
                f"expected {self._sample_rate}, got {rendered_sample_rate}"
            )
