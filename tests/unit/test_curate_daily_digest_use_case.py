from __future__ import annotations

from datetime import date

from hermes.app.runtime_config import CurateDailyDigestConfig
from hermes.app.use_cases.curate_daily_digest import CurateDailyDigestUseCase


class _DummyEmbeddingPort:
    def embed_texts(self, model: str, inputs: list[str]):
        return []


class _DummyVectorStore:
    def query_similar(self, **kwargs):
        return []

    def upsert_digest(self, **kwargs) -> None:
        return None


class _DummyLlmPort:
    def chat_structured(self, **kwargs):
        return {
            "themes": ["mercado financeiro"],
            "highlights": ["Destaque de teste"],
            "sources": ["newsletter@fonte.com"],
            "final_text": "Resumo de teste",
        }


class _DummyLogger:
    def info(self, *args, **kwargs):
        return None


def _build_use_case() -> CurateDailyDigestUseCase:
    return CurateDailyDigestUseCase(
        embedding_port=_DummyEmbeddingPort(),
        vector_store=_DummyVectorStore(),
        llm_port=_DummyLlmPort(),
        logger=_DummyLogger(),
        config=CurateDailyDigestConfig(),
    )


def test_enrich_final_text_expands_short_summary_to_richer_output() -> None:
    use_case = _build_use_case()

    enriched = use_case._enrich_final_text(
        "Dia de pregão misto com volatilidade elevada.",
        date_ref=date(2026, 4, 16),
        highlights=[
            "Ibovespa oscilou com peso de bancos e commodities, refletindo incerteza sobre juros globais.",
            "Curva de juros local abriu na ponta longa após falas mais duras de autoridades monetarias.",
            "Dolar ganhou força no intraday com rotação para ativos defensivos em mercados emergentes.",
            "Petroleo subiu com risco geopolítico, beneficiando petroleiras e pressionando custos de transporte.",
            "Setor de varejo sentiu piora de premissas de consumo e revisão de lucro para o proximo trimestre.",
            "Bitcoin testou suporte tecnico importante com queda de liquidez e maior dispersao entre exchanges.",
            "Treasuries longos voltaram a subir rendimento, afetando fluxo para bolsas fora dos EUA.",
        ],
        sources=["newsletter@neofeed.com.br", "https://www.infomoney.com.br/mercados"],
    )

    assert len(enriched) >= 720
    assert "Sinais relevantes do dia" in enriched
    assert "Implicacoes para monitorar no curto prazo" in enriched
    assert "Referencias consideradas na consolidacao" in enriched


def test_enrich_final_text_keeps_long_content_without_overexpanding() -> None:
    use_case = _build_use_case()

    long_text = (
        "O mercado local iniciou a sessao com postura defensiva, mas ganhou tracao ao longo do dia com "
        "recomposicao parcial de risco em setores de maior liquidez. "
        "A leitura de inflacao corrente trouxe alivio pontual, embora o nucleo ainda sugira cautela no ciclo de juros. "
        "No cambio, o real alternou sinais conforme variacao dos rendimentos dos titulos americanos e fluxo para emergentes. "
        "Em acoes, bancos e energia deram sustentacao ao indice enquanto varejo e construcao seguiram mais pressionados. "
        "No externo, commodities sensiveis a atividade mostraram recuperacao moderada, sem caracterizar reversao estrutural. "
        "Para a carteira tática, o saldo do dia indica priorizar qualidade, liquidez e disciplina de risco em entradas novas."
    )

    enriched = use_case._enrich_final_text(
        long_text,
        date_ref=date(2026, 4, 16),
        highlights=[
            "Ibovespa fechou em alta moderada com melhor desempenho relativo de bancos.",
            "Dolar encerrou perto da estabilidade com volatilidade ao longo da tarde.",
        ],
        sources=["newsletter@neofeed.com.br"],
    )

    assert len(enriched) >= 720
    assert "Sinais relevantes do dia" not in enriched
