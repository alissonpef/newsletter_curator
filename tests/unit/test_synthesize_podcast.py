from __future__ import annotations

from datetime import date
from pathlib import Path

from hermes.app.runtime_config import PodcastSynthesisConfig
from hermes.app.use_cases.synthesize_podcast import SynthesizePodcastUseCase
from hermes.core.entities import DailyDigest


class DummyLogger:
    def info(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None


class FailingLlm:
    def chat_structured(self, **kwargs):
        raise RuntimeError("ollama unavailable")


class CaptureTts:
    def __init__(self) -> None:
        self.received_script = ""

    def synthesize(self, script_text: str, output_path: Path) -> Path:
        self.received_script = script_text
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-wav")
        return output_path


def test_synthesize_podcast_uses_clean_fallback_script_when_llm_fails(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    use_case = SynthesizePodcastUseCase(
        llm_port=FailingLlm(),
        tts_port=CaptureTts(),
        logger=DummyLogger(),
        config=PodcastSynthesisConfig(
            chat_model="qwen3.5:9b",
            output_dir=Path("data/outputs/audio"),
            script_prompt="Crie um roteiro curto de podcast em portugues.",
        ),
    )
    capture_tts = use_case._tts_port

    digest = DailyDigest(
        run_id="run-1",
        date_ref=date(2026, 4, 15),
        themes=["Panorama do mercado"],
        highlights=[
            "Mercado reagiu bem ao anuncio de novos investimentos.",
            "Dolar caiu e alivio aparece no custo de importados.",
            "https://example.com/link-muito-grande?utm_source=test",
        ],
        sources=["source@example.com"],
        final_text="Resumo curto",
    )

    artifact = use_case.execute(run_id="run-1", digest=digest)

    assert artifact.path.exists()
    assert artifact.path.name.startswith("2026-04-15-podcast-panorama-do-mercado")
    assert len(capture_tts.received_script) >= 80
    assert "\n" not in capture_tts.received_script
    assert "http" not in capture_tts.received_script.lower()
