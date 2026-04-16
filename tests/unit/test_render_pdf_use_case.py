from __future__ import annotations

from datetime import date
from pathlib import Path

from hermes.app.runtime_config import RenderPdfConfig
from hermes.app.use_cases.render_pdf import RenderPdfUseCase
from hermes.core.entities import DailyDigest


class DummyLogger:
    def info(self, *args, **kwargs):
        return None


class CapturePdfPort:
    def __init__(self) -> None:
        self.last_output_path: Path | None = None

    def render(self, template_name: str, context: dict, output_path: Path) -> Path:
        self.last_output_path = output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"pdf")
        return output_path


def _digest(theme: str) -> DailyDigest:
    return DailyDigest(
        run_id="run-1",
        date_ref=date(2026, 4, 15),
        themes=[theme],
        highlights=["Destaque importante"],
        sources=["newsletter@neofeed.com.br"],
        final_text="Texto final",
    )


def test_render_pdf_uses_date_and_theme_in_filename(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    port = CapturePdfPort()
    use_case = RenderPdfUseCase(
        pdf_port=port,
        logger=DummyLogger(),
        config=RenderPdfConfig(template_name="newsletter.html.j2", output_dir=Path("data/outputs/pdf")),
    )

    artifact = use_case.execute(run_id="run-1", digest=_digest("Mercado em alta hoje"))

    assert artifact.path.exists()
    assert artifact.path.name == "2026-04-15-mercado-em-alta-hoje.pdf"


def test_render_pdf_adds_version_suffix_when_file_exists(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    existing = Path("data/outputs/pdf/2026-04-15-mercado-em-alta-hoje.pdf")
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b"old")

    port = CapturePdfPort()
    use_case = RenderPdfUseCase(
        pdf_port=port,
        logger=DummyLogger(),
        config=RenderPdfConfig(template_name="newsletter.html.j2", output_dir=Path("data/outputs/pdf")),
    )

    artifact = use_case.execute(run_id="run-2", digest=_digest("Mercado em alta hoje"))

    assert artifact.path.name == "2026-04-15-mercado-em-alta-hoje-v2.pdf"
