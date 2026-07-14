from __future__ import annotations

from typing import Any

import requests

from hermes.core.digest_document import (
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
        return (
            "Você é o editor-chefe de um briefing executivo matinal para um "
            "leitor profissional do mercado.\n\n"
            "Objetivo:\n"
            "- consolidar newsletters financeiras em um resumo elegante e sem ruído;\n"
            "- remover duplicidade factual e textual;\n"
            "- escrever em português do Brasil com tom sóbrio, direto e inteligente;\n"
            "- jamais reproduzir links, rodapés, banners, chamadas promocionais, botões, "
            "créditos de e-mail ou instruções de assinatura.\n\n"
            "Regras absolutas:\n"
            "- Não use caixa alta em títulos.\n"
            "- Não deixe linhas em branco extras.\n"
            "- Não repita o mesmo fato com frases diferentes.\n"
            "- Quando o mesmo tema aparecer em mais de uma fonte, consolide em um único tópico.\n"
            "- Cada fonte deve virar no máximo um tema principal; não separe um único e-mail "
            "em vários tópicos.\n"
            "- Se uma fonte tiver subtítulos ou desdobramentos, use isso como contexto do mesmo "
            "tópico, não como um novo tópico.\n"
            "- Evite adjetivação vazia e frases longas.\n"
            "- Se houver informação insuficiente para um tópico, "
            "omita o tópico em vez de inventar.\n\n"
            "Saída obrigatória, exatamente em Markdown, sem texto antes ou depois:\n\n"
            "# Tese do dia\n"
            "<um parágrafo curto com a leitura central do dia>\n\n"
            "# Panorama executivo\n"
            "<um parágrafo curto explicando o quadro geral>\n\n"
            "# Leituras prioritárias\n"
            "- <3 a 5 bullets objetivos, sem repetir temas>\n\n"
            "# Temas em foco\n"
            "## <título em Title Case>\n"
            "<um parágrafo curto>\n"
            "Impacto: <uma frase objetiva>\n"
            "Sinal: <Alta, Média ou Baixa>\n\n"
            "## <repita para 3 a 5 temas realmente relevantes, com no máximo um tema por fonte>\n\n"
            "# Fechamento\n"
            "<um parágrafo curto com o que merece monitoramento a seguir>\n\n"
            "Conteúdo limpo das newsletters:\n"
            f"{prompt_payload}\n"
        )

    def generate_summary(self, newsletters: list[dict[str, str]]) -> dict[str, Any]:
        source_packets = build_source_packets(newsletters)
        if not source_packets:
            raise ValueError("No content found to summarize.")

        prompt_payload = render_prompt_payload(source_packets)
        prompt = self._build_prompt(prompt_payload)

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

        if not summary_data.get("plainText"):
            summary_data["plainText"] = summary_to_plain_text(summary_data)
        if not summary_data.get("ttsScript"):
            summary_data["ttsScript"] = summary_data["plainText"]

        summary_data["sourceCount"] = len(source_packets)
        if not summary_data.get("paragraphCount"):
            summary_data["paragraphCount"] = sum(
                len(packet.get("highlights", [])) for packet in source_packets
            )

        return summary_data
