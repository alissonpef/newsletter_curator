from __future__ import annotations

from typing import Any, Dict, List

import requests

from hermes.core.digest_document import (
    build_fallback_summary,
    parse_summary_markdown,
    summary_to_plain_text,
)
from hermes.core.interfaces import LlmPort
from hermes.infra.adapters.newsletter_cleaner import (
    build_source_packets,
    render_prompt_payload,
)


class OllamaAdapter(LlmPort):
    def __init__(self, base_url: str, model: str, timeout: int):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def _build_prompt(self, prompt_payload: str) -> str:
        return f"""Você é o editor-chefe de um briefing executivo matinal para um leitor profissional do mercado.

Objetivo:
- consolidar newsletters financeiras em um resumo elegante e sem ruído;
- remover duplicidade factual e textual;
- escrever em português do Brasil com tom sóbrio, direto e inteligente;
- jamais reproduzir links, rodapés, banners, chamadas promocionais, botões, créditos de e-mail ou instruções de assinatura.

Regras absolutas:
- Não use caixa alta em títulos.
- Não deixe linhas em branco extras.
- Não repita o mesmo fato com frases diferentes.
- Quando o mesmo tema aparecer em mais de uma fonte, consolide em um único tópico.
- Cada fonte deve virar no máximo um tema principal; não separe um único e-mail em vários tópicos.
- Se uma fonte tiver subtítulos ou desdobramentos, use isso como contexto do mesmo tópico, não como um novo tópico.
- Evite adjetivação vazia e frases longas.
- Se houver informação insuficiente para um tópico, omita o tópico em vez de inventar.

Saída obrigatória, exatamente em Markdown, sem texto antes ou depois:

# Tese do dia
<um parágrafo curto com a leitura central do dia>

# Panorama executivo
<um parágrafo curto explicando o quadro geral>

# Leituras prioritárias
- <3 a 5 bullets objetivos, sem repetir temas>

# Temas em foco
## <título em Title Case>
<um parágrafo curto>
Impacto: <uma frase objetiva>
Sinal: <Alta, Média ou Baixa>

## <repita para 3 a 5 temas realmente relevantes, com no máximo um tema por fonte>

# Fechamento
<um parágrafo curto com o que merece monitoramento a seguir>

Conteúdo limpo das newsletters:
{prompt_payload}
"""

    def generate_summary(self, newsletters: List[Dict[str, str]]) -> Dict[str, Any]:
        source_packets = build_source_packets(newsletters)
        fallback = build_fallback_summary(source_packets)

        if not source_packets:
            return fallback

        prompt_payload = render_prompt_payload(source_packets)
        prompt = self._build_prompt(prompt_payload)

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.2,
                        "top_p": 0.85,
                        "num_ctx": 12288,
                    },
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            markdown = response.json().get("response", "")
            summary_data = parse_summary_markdown(markdown)
        except requests.exceptions.RequestException as exc:
            print(f"Ollama error: {exc}. Using fallback summary.")
            summary_data = fallback
        except Exception as exc:
            print(f"Summary parsing error: {exc}. Using fallback summary.")
            summary_data = fallback

        if not summary_data.get("plainText"):
            summary_data["plainText"] = summary_to_plain_text(summary_data)
        if not summary_data.get("ttsScript"):
            summary_data["ttsScript"] = summary_data["plainText"]

        summary_data["sourceCount"] = len(source_packets)
        if not summary_data.get("paragraphCount"):
            summary_data["paragraphCount"] = sum(
                len(packet.get("highlights", [])) for packet in source_packets
            )

        if not summary_data.get("topics"):
            summary_data["topics"] = fallback.get("topics", [])
        if not summary_data.get("keyPoints"):
            summary_data["keyPoints"] = fallback.get("keyPoints", [])
        if not summary_data.get("thesis"):
            summary_data["thesis"] = fallback.get("thesis", "")
        if not summary_data.get("executiveSummary"):
            summary_data["executiveSummary"] = fallback.get("executiveSummary", "")
        if not summary_data.get("closing"):
            summary_data["closing"] = fallback.get("closing", "")
        if not summary_data.get("plainText"):
            summary_data["plainText"] = fallback.get("plainText", "")
        if not summary_data.get("ttsScript"):
            summary_data["ttsScript"] = fallback.get("ttsScript", "")

        return summary_data
