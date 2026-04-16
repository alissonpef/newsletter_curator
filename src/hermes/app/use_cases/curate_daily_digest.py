from datetime import date
import re
from urllib.parse import urlparse

from ...app.runtime_config import CurateDailyDigestConfig
from ...core.entities import DailyDigest
from ...core.policies import resolve_namespace
from ...infra.text_sanitizer import TextSanitizer
from ...ports.embedding_port import EmbeddingPort
from ...ports.llm_port import LlmPort
from ...ports.vector_store_port import VectorStorePort


class CurateDailyDigestUseCase:
    _MIN_FINAL_TEXT_CHARS = 720
    _MAX_FINAL_TEXT_CHARS = 2200

    def __init__(
        self,
        embedding_port: EmbeddingPort,
        vector_store: VectorStorePort,
        llm_port: LlmPort,
        logger,
        config: CurateDailyDigestConfig,
    ) -> None:
        self._embedding_port = embedding_port
        self._vector_store = vector_store
        self._llm_port = llm_port
        self._logger = logger
        self._config = config
        self._text_sanitizer = TextSanitizer()

    def _strip_markdown_links(self, text: str) -> str:
        return re.sub(r"\[([^\]]+)\]\((?:https?://)?[^)]+\)", r"\1", str(text))

    def _clean_for_digest(self, text: str) -> str:
        raw = self._strip_markdown_links(text)
        raw = re.sub(r"^\s*[•\-*]+\s*", "", raw)
        cleaned = self._text_sanitizer.sanitize(raw, profile="summary")
        cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
        cleaned = re.sub(r"\.{4,}", ".", cleaned)
        if cleaned.endswith("..."):
            cleaned = cleaned[:-3].rstrip()
        return cleaned

    def _trim_without_ellipsis(self, text: str, max_chars: int) -> str:
        compact = self._clean_for_digest(text)
        if len(compact) <= max_chars:
            return compact

        cut = compact[:max_chars]
        sentence_end = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"), cut.rfind(";"))
        if sentence_end >= int(max_chars * 0.55):
            return cut[: sentence_end + 1].strip()

        space_end = cut.rfind(" ")
        trimmed = cut[:space_end].strip() if space_end > 0 else cut.strip()
        if trimmed and trimmed[-1].isalnum():
            return f"{trimmed}."
        return trimmed

    def _normalize_source(self, value: str) -> str | None:
        raw = self._strip_markdown_links(value).strip()
        if not raw:
            return None

        urls = re.findall(r"https?://\S+", raw, flags=re.IGNORECASE)
        for url in urls:
            host = urlparse(url).netloc.strip().lower()
            if host.startswith("www."):
                host = host[4:]
            raw = raw.replace(url, host or "")

        cleaned = self._clean_for_digest(raw).strip(" -,:;")
        if not cleaned:
            return None

        if len(cleaned) > 120:
            cleaned = self._trim_without_ellipsis(cleaned, max_chars=120)
        return cleaned

    def _build_llm_context(
        self,
        snippets: list[str],
        *,
        max_snippets: int = 10,
        max_chars_per_snippet: int = 560,
        max_total_chars: int = 4200,
    ) -> str:
        selected: list[str] = []
        total = 0

        for raw in snippets:
            text = self._clean_for_digest(raw)
            if not text:
                continue

            if len(text) > max_chars_per_snippet:
                text = self._trim_without_ellipsis(text, max_chars=max_chars_per_snippet)

            next_size = total + len(text)
            if selected and next_size > max_total_chars:
                break
            if not selected and len(text) > max_total_chars:
                text = self._trim_without_ellipsis(text, max_chars=max_total_chars)
                selected.append(text)
                break

            selected.append(text)
            total += len(text)

            if len(selected) >= max_snippets:
                break

        return "\n".join(selected)

    def _normalize_key(self, text: str) -> str:
        return re.sub(r"\s+", " ", str(text).strip()).lower()

    def _sentence_count(self, text: str) -> int:
        return len(re.findall(r"[.!?](?:\s|$)", text))

    def _build_structured_points(
        self,
        highlights: list[str],
        *,
        max_points: int,
        max_chars: int,
    ) -> list[str]:
        points: list[str] = []
        seen: set[str] = set()

        for highlight in highlights:
            candidate = self._truncate_text(highlight, max_chars=max_chars).strip(" -")
            if len(candidate) < 45:
                continue
            key = self._normalize_key(candidate)
            if not key or key in seen:
                continue
            seen.add(key)
            points.append(candidate.rstrip("."))
            if len(points) >= max_points:
                break

        return points

    def _trim_final_text(self, text: str, max_chars: int) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        if len(compact) <= max_chars:
            return text.strip()

        cut = compact[:max_chars]
        sentence_end = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"), cut.rfind(";"))
        if sentence_end >= int(max_chars * 0.7):
            return cut[: sentence_end + 1].strip()

        space_end = cut.rfind(" ")
        trimmed = cut[:space_end].strip() if space_end > 0 else cut.strip()
        if trimmed and trimmed[-1].isalnum():
            return f"{trimmed}."
        return trimmed

    def _collect_unique_snippets(self, retrieval_hits: list[dict[str, object]], max_items: int = 40) -> list[str]:
        snippets: list[str] = []
        seen: set[str] = set()

        for hit in retrieval_hits:
            raw = hit.get("text", "")
            compact = self._trim_without_ellipsis(raw, max_chars=800)
            if not compact:
                continue

            key = self._normalize_key(compact[:260])
            if not key or key in seen:
                continue

            seen.add(key)
            snippets.append(compact)
            if len(snippets) >= max_items:
                break

        return snippets

    def _truncate_text(self, text: str, max_chars: int = 280) -> str:
        return self._trim_without_ellipsis(text, max_chars=max_chars)

    def _enrich_highlights(
        self,
        highlights: list[str],
        snippets: list[str],
        *,
        min_items: int = 7,
        max_items: int = 12,
    ) -> list[str]:
        enriched: list[str] = []
        seen: set[str] = set()

        for item in highlights:
            candidate = self._truncate_text(item, max_chars=340)
            if len(candidate) < 45:
                continue
            key = self._normalize_key(candidate)
            if key in seen:
                continue
            seen.add(key)
            enriched.append(candidate)
            if len(enriched) >= max_items:
                return enriched

        for snippet in snippets:
            candidate = self._truncate_text(snippet, max_chars=360)
            if len(candidate) < 60:
                continue
            key = self._normalize_key(candidate)
            if key in seen:
                continue
            seen.add(key)
            enriched.append(candidate)
            if len(enriched) >= max_items:
                break

        if not enriched:
            return ["Sem destaques estruturados disponiveis para o dia."]

        if len(enriched) < min_items:
            # Keep what we have if the day had little signal, but avoid collapsing to only 2-3 bullets.
            return enriched
        return enriched

    def _enrich_final_text(
        self,
        final_text: str,
        *,
        date_ref: date,
        highlights: list[str],
        sources: list[str],
    ) -> str:
        compact = re.sub(r"\s+", " ", final_text).strip()
        compact = self._clean_for_digest(compact)
        compact = re.sub(r"(?i)\bdestaques?\s+expandidos?:\s*", "", compact)
        compact = re.sub(r"(?i)\bfontes?\s+mencionadas?:\s*", "", compact)

        if len(compact) >= self._MIN_FINAL_TEXT_CHARS and self._sentence_count(compact) >= 6:
            return self._trim_final_text(compact, max_chars=self._MAX_FINAL_TEXT_CHARS)

        points = self._build_structured_points(
            highlights,
            max_points=8,
            max_chars=220,
        )

        intro = compact or (
            f"Panorama do dia {date_ref.isoformat()} com consolidacao das newsletters monitoradas."
        )

        if len(intro) < 220 and points:
            complement = "; ".join(points[:2])
            if complement:
                intro = (
                    f"{intro}"
                    f" O recorte de hoje mostrou sinais praticos em: {complement}."
                ).strip()

        sections: list[str] = [intro]

        if points:
            first_block = points[:4]
            first_lines = "\n".join(f"- {item}." for item in first_block)
            sections.append(f"Sinais relevantes do dia:\n{first_lines}")

            second_block = points[4:8]
            if second_block:
                second_lines = "\n".join(f"- {item}." for item in second_block)
                sections.append(f"Implicacoes para monitorar no curto prazo:\n{second_lines}")

        if sources:
            normalized_sources = [self._normalize_source(source) for source in sources]
            normalized_sources = [source for source in normalized_sources if source]
            if normalized_sources:
                sources_preview = ", ".join(normalized_sources[:8])
                sections.append(
                    "Referencias consideradas na consolidacao: "
                    f"{sources_preview}."
                )

        enriched = "\n\n".join(section.strip() for section in sections if section.strip())
        enriched = self._trim_final_text(enriched, max_chars=self._MAX_FINAL_TEXT_CHARS)

        if len(enriched) < self._MIN_FINAL_TEXT_CHARS and points:
            remaining_points = points[2:]
            if remaining_points:
                supplemental = " ".join(f"{point}." for point in remaining_points)
                enriched = self._trim_final_text(
                    f"{enriched}\n\nLeitura executiva complementar: {supplemental}",
                    max_chars=self._MAX_FINAL_TEXT_CHARS,
                )

        return enriched.strip()

    def execute(self, run_id: str, date_ref: date, topics: list[str]) -> DailyDigest:
        topic_inputs = topics if topics else [date_ref.isoformat()]

        query_embeddings = self._embedding_port.embed_texts(
            model=self._config.embed_model,
            inputs=topic_inputs,
        )

        namespace = resolve_namespace(date_ref)
        retrieval_hits = self._vector_store.query_similar(
            collection=self._config.chunks_collection,
            query_embeddings=query_embeddings,
            n_results=6,
            where={
                "$and": [
                    {"date_ref": date_ref.isoformat()},
                    {"namespace": namespace},
                ]
            },
        )

        retrieved_snippets = self._collect_unique_snippets(retrieval_hits)
        source_ids = [str(hit.get("chunk_id", "")) for hit in retrieval_hits if hit.get("chunk_id")]

        schema = {
            "type": "object",
            "properties": {
                "themes": {"type": "array", "items": {"type": "string"}},
                "highlights": {"type": "array", "items": {"type": "string"}},
                "sources": {"type": "array", "items": {"type": "string"}},
                "final_text": {"type": "string"},
            },
            "required": ["themes", "highlights", "sources", "final_text"],
        }

        context_text = self._build_llm_context(retrieved_snippets)

        prompt_text = (
            f"{self._config.consolidate_prompt}\n\n"
            f"{self._config.editorial_style_prompt}\n\n"
            "Requisito obrigatorio para final_text:\n"
            "- Escreva entre 3 e 5 paragrafos\n"
            "- Tamanho alvo entre 900 e 1600 caracteres\n"
            "- Traga contexto e implicacao pratica; evite texto telegráfico\n\n"
            f"Data de referencia: {date_ref.isoformat()}\n"
            f"Topicos guia: {', '.join(topic_inputs)}\n"
            f"Contexto:\n{context_text}"
        )

        structured = self._llm_port.chat_structured(
            model=self._config.chat_model,
            messages=[
                {
                    "role": "system",
                    "content": "Voce e um editor tecnico. Responda somente no schema JSON solicitado.",
                },
                {
                    "role": "user",
                    "content": prompt_text,
                },
            ],
            json_schema=schema,
        )

        themes = [str(item).strip() for item in structured.get("themes", []) if str(item).strip()]
        highlights = [str(item).strip() for item in structured.get("highlights", []) if str(item).strip()]
        llm_sources: list[str] = []
        for item in structured.get("sources", []):
            normalized = self._normalize_source(str(item))
            if normalized:
                llm_sources.append(normalized)
        llm_sources = list(dict.fromkeys(llm_sources))
        final_text = str(structured.get("final_text", "")).strip()

        if not themes:
            if topics:
                themes = [str(topics[0]).strip()]
            else:
                themes = ["panorama do dia"]

        if len(themes) < 4:
            for topic in topic_inputs:
                cleaned_topic = str(topic).strip()
                if cleaned_topic and cleaned_topic not in themes:
                    themes.append(cleaned_topic)
                if len(themes) >= 8:
                    break

        highlights = self._enrich_highlights(highlights, retrieved_snippets)

        resolved_sources = llm_sources if llm_sources else []
        final_text = self._enrich_final_text(
            final_text,
            date_ref=date_ref,
            highlights=highlights,
            sources=resolved_sources,
        )

        digest = DailyDigest(
            run_id=run_id,
            date_ref=date_ref,
            themes=themes,
            highlights=highlights,
            sources=resolved_sources,
            final_text=final_text,
        )

        digest_metadata = {
            "date_ref": date_ref.isoformat(),
            "namespace": namespace,
        }
        if digest.themes:
            digest_metadata["themes_csv"] = " | ".join(digest.themes[:12])
        if digest.sources:
            digest_metadata["sources_csv"] = " | ".join(digest.sources[:12])

        self._vector_store.upsert_digest(
            collection=self._config.digests_collection,
            digest_id=run_id,
            digest_text=digest.final_text,
            metadata=digest_metadata,
        )

        if digest.themes:
            topic_memory_id = f"topic-memory::{run_id}"
            topic_memory_text = " | ".join(digest.themes)
            self._vector_store.upsert_digest(
                collection=self._config.topic_memory_collection,
                digest_id=topic_memory_id,
                digest_text=topic_memory_text,
                metadata={
                    "date_ref": date_ref.isoformat(),
                    "namespace": namespace,
                    "run_id": run_id,
                    "themes_csv": " | ".join(digest.themes[:12]),
                },
            )

        self._logger.info(
            "curated daily digest",
            extra={"run_id": run_id, "themes": len(digest.themes), "sources": len(digest.sources)},
        )
        return digest
