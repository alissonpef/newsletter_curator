from __future__ import annotations

import subprocess
from pathlib import Path

from hermes.adapters.tts.piper_tts_adapter import PiperTtsAdapter


class _Completed:
    def __init__(self) -> None:
        self.returncode = 0
        self.stdout = b""
        self.stderr = b""


def test_piper_adapter_does_not_pass_unsupported_sample_rate_flag(monkeypatch, tmp_path) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(command, input, stdout, stderr, check):
        captured["command"] = command
        output_index = command.index("--output_file") + 1
        output_path = Path(command[output_index])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-wav")
        return _Completed()

    monkeypatch.setattr(subprocess, "run", fake_run)

    adapter = PiperTtsAdapter(
        piper_executable="piper",
        model_path=Path("models/pt_BR-voice.onnx"),
        sample_rate=22050,
    )

    rendered = adapter.synthesize(
        script_text="Linha 1\nLinha 2",
        output_path=tmp_path / "out.wav",
    )

    assert rendered.exists()
    assert "--sample_rate" not in captured["command"]
