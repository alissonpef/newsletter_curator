from __future__ import annotations

from datetime import date
from pathlib import Path

from hermes.adapters.pdf.weasyprint_renderer import WeasyprintRenderer
from hermes.core.entities import DailyDigest


def test_weasyprint_renderer_generates_valid_pdf_with_multiline_final_text(tmp_path) -> None:
    renderer = WeasyprintRenderer(template_dir=Path("src/hermes/templates"))

    digest = DailyDigest(
        run_id="run-pdf-smoke",
        date_ref=date(2026, 4, 16),
        themes=["mercado financeiro", "juros", "cambio"],
        highlights=[
            "Curva local abriu na ponta longa e fechou com volatilidade elevada.",
            "Dolar oscilou acompanhando movimento de treasuries.",
        ],
        sources=["newsletter@neofeed.com.br"],
        final_text=(
            "Panorama consolidado do dia com foco em risco e direcao tática.\n\n"
            "Sinais relevantes do dia:\n"
            "- Abertura da curva longa com ajuste de premio de risco.\n"
            "- Compressao parcial no fechamento com recomposicao de fluxo local.\n\n"
            "Implicacoes para monitorar no curto prazo:\n"
            "- Evitar concentracao excessiva em setores mais sensiveis a juros reais.\n"
            "- Priorizar ativos com liquidez e capacidade de repasse de precos."
        ),
    )

    output_path = tmp_path / "digest.pdf"
    rendered_path = renderer.render(
        template_name="newsletter.html.j2",
        context={"digest": digest},
        output_path=output_path,
    )

    assert rendered_path.exists()
    pdf_header = rendered_path.read_bytes()[:4]
    assert pdf_header == b"%PDF"
    assert rendered_path.stat().st_size > 1024
