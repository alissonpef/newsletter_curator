from __future__ import annotations

import re
from dataclasses import replace
from datetime import date, timedelta
from uuid import uuid4

from .runtime_config import PipelineRuntimeConfig
from ..core.errors import LlmUnavailableError, StateLockError
from ..core.entities import DailyDigest, EmailItem, RunState
from ..infra.text_sanitizer import TextSanitizer


class DailyPipelineOrchestrator:
    def __init__(
        self,
        fetch_new_emails_uc,
        parse_and_clean_uc,
        index_embeddings_uc,
        curate_daily_digest_uc,
        render_pdf_uc,
        send_kindle_email_uc,
        synthesize_podcast_uc,
        persist_run_state_uc,
        state_store,
        lock,
        clock,
        logger,
        build_market_snapshot_uc=None,
        runtime_config: PipelineRuntimeConfig | None = None,
        text_sanitizer: TextSanitizer | None = None,
    ) -> None:
        self._fetch_new_emails_uc = fetch_new_emails_uc
        self._parse_and_clean_uc = parse_and_clean_uc
        self._index_embeddings_uc = index_embeddings_uc
        self._curate_daily_digest_uc = curate_daily_digest_uc
        self._render_pdf_uc = render_pdf_uc
        self._send_kindle_email_uc = send_kindle_email_uc
        self._synthesize_podcast_uc = synthesize_podcast_uc
        self._persist_run_state_uc = persist_run_state_uc
        self._state_store = state_store
        self._lock = lock
        self._clock = clock
        self._logger = logger
        self._build_market_snapshot_uc = build_market_snapshot_uc
        self._runtime_config = runtime_config or PipelineRuntimeConfig()
        self._text_sanitizer = text_sanitizer or TextSanitizer()

    def _normalize_for_dedupe(self, text: str) -> str:
        return re.sub(r"[^\w\s]", " ", text.lower(), flags=re.UNICODE).strip()

    def _compress_subject(self, subject: str, max_chars: int = 96) -> str:
        cleaned = re.sub(r"\s+", " ", subject).strip(" -|:")
        if len(cleaned) <= max_chars:
            return cleaned
        shortened = cleaned[:max_chars].rsplit(" ", 1)[0].strip()
        return shortened if shortened else cleaned[:max_chars]

    def _new_run_id(self, date_ref: date) -> str:
        return f"{date_ref.isoformat()}-{uuid4().hex[:8]}"

    def _clean_text_for_fallback(self, text: str) -> str:
        return self._text_sanitizer.sanitize(text, profile="fallback")

    def _refresh_run_lock(self, run_key: str) -> None:
        if not hasattr(self._state_store, "refresh_run_lock"):
            return
        try:
            self._state_store.refresh_run_lock(run_key)
        except Exception as exc:
            self._logger.warning(
                "failed to refresh run lock",
                extra={"run_key": run_key, "error": str(exc)},
            )

    def _build_snippet(self, text: str, max_chars: int = 220) -> str:
        cleaned = self._clean_text_for_fallback(text)
        if not cleaned:
            return ""

        sentences = re.split(r"(?<=[.!?])\s+", cleaned)
        selected: list[str] = []
        selected_norms: list[str] = []
        for sentence in sentences:
            candidate = sentence.strip(" -")
            if len(candidate) < 30:
                continue
            lowered = candidate.lower()
            if any(token in lowered for token in ["ver imagem", "caption", "browser", "unsubscribe"]):
                continue

            normalized = self._normalize_for_dedupe(candidate)
            if not normalized:
                continue
            if any(
                normalized == previous
                or normalized in previous
                or previous in normalized
                for previous in selected_norms
            ):
                continue

            selected.append(candidate)
            selected_norms.append(normalized)
            if len(" ".join(selected)) >= max_chars:
                break

        snippet = " ".join(selected) if selected else cleaned
        if len(snippet) <= max_chars:
            return snippet
        shortened = snippet[:max_chars]
        sentence_end = max(shortened.rfind("."), shortened.rfind("!"), shortened.rfind("?"), shortened.rfind(";"))
        if sentence_end >= int(max_chars * 0.55):
            return shortened[: sentence_end + 1].strip()
        space_end = shortened.rfind(" ")
        trimmed = shortened[:space_end].strip() if space_end > 0 else shortened.strip()
        if trimmed and trimmed[-1].isalnum():
            return f"{trimmed}."
        return trimmed

    def _truncate_text(self, text: str, max_chars: int = 240) -> str:
        compact = re.sub(r"\s+", " ", str(text).strip())
        if len(compact) <= max_chars:
            return compact
        shortened = compact[:max_chars]
        sentence_end = max(shortened.rfind("."), shortened.rfind("!"), shortened.rfind("?"), shortened.rfind(";"))
        if sentence_end >= int(max_chars * 0.55):
            return shortened[: sentence_end + 1].strip()
        space_end = shortened.rfind(" ")
        trimmed = shortened[:space_end].strip() if space_end > 0 else shortened.strip()
        if trimmed and trimmed[-1].isalnum():
            return f"{trimmed}."
        return trimmed

    def _extract_supporting_points(
        self,
        text: str,
        *,
        max_points: int = 2,
        max_chars: int = 220,
    ) -> list[str]:
        cleaned = self._clean_text_for_fallback(text)
        if not cleaned:
            return []

        points: list[str] = []
        seen: set[str] = set()
        for sentence in re.split(r"(?<=[.!?])\s+", cleaned):
            candidate = sentence.strip(" -")
            if len(candidate) < 55:
                continue

            lowered = candidate.lower()
            if any(token in lowered for token in ["ver imagem", "caption", "browser", "unsubscribe"]):
                continue

            key = self._normalize_for_dedupe(candidate)
            if not key or key in seen:
                continue

            seen.add(key)
            points.append(self._truncate_text(candidate, max_chars=max_chars))
            if len(points) >= max_points:
                break

        return points

    def _build_fallback_digest(self, run_id: str, date_ref: date, emails: list[EmailItem]) -> DailyDigest:
        if not emails:
            return DailyDigest(
                run_id=run_id,
                date_ref=date_ref,
                themes=["Sem newsletters do dia"],
                highlights=["Nenhuma newsletter correspondente aos filtros foi encontrada para hoje."],
                sources=[],
                final_text=(
                    "Nao foram encontradas newsletters no dia de referencia para os remetentes permitidos."
                ),
            )

        highlights: list[str] = []
        themes: list[str] = []
        sources_seen: set[str] = set()
        themes_seen: set[str] = set()
        highlights_seen: set[str] = set()
        sources: list[str] = []

        for item in emails:
            subject = self._compress_subject(item.subject.strip() or "Sem assunto")
            snippet = self._build_snippet(item.body_text, max_chars=420)
            highlight = f"{subject}: {snippet}" if snippet else subject

            theme_key = self._normalize_for_dedupe(subject)
            if theme_key and theme_key not in themes_seen:
                themes_seen.add(theme_key)
                themes.append(subject)

            highlight_key = self._normalize_for_dedupe(highlight)
            if highlight_key and highlight_key not in highlights_seen:
                highlights_seen.add(highlight_key)
                highlights.append(highlight)

            for point in self._extract_supporting_points(item.body_text, max_points=2, max_chars=220):
                detailed_highlight = f"{subject} - {point}"
                detailed_key = self._normalize_for_dedupe(detailed_highlight)
                if highlight_key and (
                    detailed_key == highlight_key
                    or detailed_key in highlight_key
                    or highlight_key in detailed_key
                ):
                    continue
                if detailed_key and detailed_key not in highlights_seen:
                    highlights_seen.add(detailed_key)
                    highlights.append(detailed_highlight)
                if len(highlights) >= 12:
                    break

            source = item.sender.strip()
            if source and source not in sources_seen:
                sources_seen.add(source)
                sources.append(source)

            if len(highlights) >= 12:
                continue

        top_themes = ", ".join(themes[:3]) if themes else "sem temas dominantes"
        highlights_preview = "; ".join(line.split(":", 1)[0].strip() for line in highlights[:4])
        highlights_block = "\n".join(f"- {line}" for line in highlights[:10])
        final_text = (
            f"Panorama do dia {date_ref.isoformat()}.\n\n"
            f"Foram consolidados {len(highlights)} pontos relevantes de {len(sources)} fontes monitoradas. "
            f"Temas centrais: {top_themes}.\n\n"
            f"Leitura rapida: {highlights_preview}.\n\n"
            f"Pontos observados no material do dia:\n{highlights_block}"
        )

        return DailyDigest(
            run_id=run_id,
            date_ref=date_ref,
            themes=themes[:8],
            highlights=highlights[:12],
            sources=sources,
            final_text=final_text,
        )

    def _enrich_digest_with_market_snapshot(self, run_id: str, digest: DailyDigest) -> DailyDigest:
        if self._build_market_snapshot_uc is None:
            return digest

        try:
            snapshot = self._build_market_snapshot_uc.execute(run_id=run_id)
        except Exception as exc:
            self._logger.warning(
                "failed to collect market snapshot",
                extra={"run_id": run_id, "error": str(exc)},
            )
            return digest

        if not snapshot:
            return digest

        return replace(digest, market_snapshot=snapshot)

    def run_daily(self, date_ref: date | None = None, dry_run: bool = False) -> RunState:
        ref_date = date_ref or self._clock.today_local()
        run_id = self._new_run_id(ref_date)
        run_key = ref_date.isoformat()
        exact_date_fetch = date_ref is not None

        mailbox = self._runtime_config.mailbox
        search_strategy = self._runtime_config.search_strategy
        since_hours_back = self._runtime_config.since_hours_back
        negative_keywords = list(self._runtime_config.negative_keywords)
        allowed_senders = list(self._runtime_config.allowed_senders)
        topics = list(self._runtime_config.topics)
        kindle_address = self._runtime_config.kindle_address.strip()

        since = None
        if since_hours_back is not None:
            since = self._clock.now_utc() - timedelta(hours=int(since_hours_back))

        if not self._state_store.acquire_run_lock(run_key):
            raise StateLockError("a run is already active for this date window")

        try:
            with self._lock:
                self._persist_run_state_uc.start(run_id=run_id, date_ref=ref_date)

                self._persist_run_state_uc.checkpoint(run_id=run_id, checkpoint="fetch_new_emails")
                self._refresh_run_lock(run_key)
                raw_emails = self._fetch_new_emails_uc.execute(
                    run_id=run_id,
                    mailbox=mailbox,
                    search_strategy=search_strategy,
                    since=since,
                    reference_date=ref_date if exact_date_fetch else None,
                )

                self._persist_run_state_uc.checkpoint(run_id=run_id, checkpoint="parse_and_clean")
                self._refresh_run_lock(run_key)
                emails = self._parse_and_clean_uc.execute(
                    run_id=run_id,
                    date_ref=ref_date,
                    raw_emails=raw_emails,
                    negative_keywords=negative_keywords,
                    allowed_senders=allowed_senders,
                    include_previously_processed=True,
                )

                try:
                    self._persist_run_state_uc.checkpoint(run_id=run_id, checkpoint="index_embeddings")
                    self._refresh_run_lock(run_key)
                    self._index_embeddings_uc.execute(run_id=run_id, date_ref=ref_date, emails=emails)

                    self._persist_run_state_uc.checkpoint(run_id=run_id, checkpoint="curate_daily_digest")
                    self._refresh_run_lock(run_key)
                    digest = self._curate_daily_digest_uc.execute(
                        run_id=run_id,
                        date_ref=ref_date,
                        topics=topics,
                    )
                except LlmUnavailableError as exc:
                    self._logger.warning(
                        "ollama unavailable, using fallback digest",
                        extra={"run_id": run_id, "error": str(exc)},
                    )
                    self._persist_run_state_uc.checkpoint(
                        run_id=run_id,
                        checkpoint="curate_daily_digest_fallback",
                    )
                    digest = self._build_fallback_digest(run_id=run_id, date_ref=ref_date, emails=emails)

                if self._build_market_snapshot_uc is not None:
                    self._persist_run_state_uc.checkpoint(run_id=run_id, checkpoint="collect_market_snapshot")
                    self._refresh_run_lock(run_key)
                    digest = self._enrich_digest_with_market_snapshot(run_id=run_id, digest=digest)

                self._persist_run_state_uc.checkpoint(run_id=run_id, checkpoint="render_pdf")
                self._refresh_run_lock(run_key)
                pdf_artifact = self._render_pdf_uc.execute(run_id=run_id, digest=digest)

                if dry_run or not self._runtime_config.send_kindle:
                    self._persist_run_state_uc.checkpoint(
                        run_id=run_id,
                        checkpoint="send_kindle_email_skipped",
                    )
                else:
                    self._persist_run_state_uc.checkpoint(run_id=run_id, checkpoint="send_kindle_email")
                    if not kindle_address:
                        raise RuntimeError("KINDLE_ADDRESS is required for non-dry-run execution")

                    self._refresh_run_lock(run_key)
                    self._send_kindle_email_uc.execute(
                        run_id=run_id,
                        pdf_path=pdf_artifact.path,
                        kindle_address=kindle_address,
                        subject=f"Newsletter Curator Digest {ref_date.isoformat()}",
                    )

                if dry_run or not self._runtime_config.generate_podcast:
                    self._persist_run_state_uc.checkpoint(
                        run_id=run_id,
                        checkpoint="synthesize_podcast_skipped",
                    )
                else:
                    self._persist_run_state_uc.checkpoint(run_id=run_id, checkpoint="synthesize_podcast")
                    self._refresh_run_lock(run_key)
                    self._synthesize_podcast_uc.execute(run_id=run_id, digest=digest)

                return self._persist_run_state_uc.finish(run_id=run_id, status="succeeded")
        except Exception as exc:
            self._logger.exception("daily pipeline failed", extra={"run_id": run_id})
            return self._persist_run_state_uc.finish(run_id=run_id, status="failed", error=str(exc))
        finally:
            self._state_store.release_run_lock(run_key)

    def replay_missed_runs(self, days_back: int) -> list[RunState]:
        recovered_states: list[RunState] = []
        missed_dates = self._persist_run_state_uc.recover_missed_dates(days_back)

        for missing_date in missed_dates:
            state = self.run_daily(date_ref=missing_date, dry_run=False)
            recovered_states.append(state)

        return recovered_states
