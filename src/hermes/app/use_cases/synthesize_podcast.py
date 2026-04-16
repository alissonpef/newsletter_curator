import hashlib

from ...app.runtime_config import PodcastSynthesisConfig
from ...core.entities import DailyDigest, MediaArtifact
from ...infra.artifact_naming import ArtifactNamingService
from ...infra.text_sanitizer import TextSanitizer
from ...ports.llm_port import LlmPort
from ...ports.tts_port import TtsPort


class SynthesizePodcastUseCase:
    def __init__(
        self,
        llm_port: LlmPort,
        tts_port: TtsPort,
        logger,
        config: PodcastSynthesisConfig,
        artifact_naming: ArtifactNamingService | None = None,
        text_sanitizer: TextSanitizer | None = None,
    ) -> None:
        self._llm_port = llm_port
        self._tts_port = tts_port
        self._logger = logger
        self._config = config
        self._artifact_naming = artifact_naming or ArtifactNamingService()
        self._text_sanitizer = text_sanitizer or TextSanitizer()

    def _build_fallback_script(self, digest: DailyDigest) -> str:
        highlights = digest.highlights[:6]
        if highlights:
            opening = (
                f"Oi, aqui e o Hermes. Seja bem-vindo ao seu podcast diario de newsletters de "
                f"{digest.date_ref.isoformat()}."
            )
            items = " ".join(
                f"No bloco {idx + 1}, o destaque foi: {item}."
                for idx, item in enumerate(highlights)
            )
            closing = (
                "Eu volto no proximo episodio com os pontos mais importantes para voce comecar o dia informado."
            )
            return (
                f"{opening} "
                f"Hoje eu separei {len(digest.highlights)} destaques principais. "
                f"{items} "
                f"{closing}"
            )
        return digest.final_text or (
            f"Oi, aqui e o Hermes com o seu resumo do dia {digest.date_ref.isoformat()}. "
            "Hoje tivemos poucos sinais relevantes nas newsletters monitoradas. "
            "No proximo episodio eu trago uma analise mais completa."
        )

    def _build_output_path(self, digest: DailyDigest):
        base_hint = digest.themes[0] if digest.themes else "newsletter"
        return self._artifact_naming.build_versioned_path(
            output_dir=self._config.output_dir,
            date_ref=digest.date_ref,
            hint=base_hint,
            extension="wav",
            stem_prefix="podcast",
            default_hint="newsletter",
        )

    def _sanitize_for_tts(self, text: str) -> str:
        return self._text_sanitizer.sanitize(text, profile="tts")

    def execute(self, run_id: str, digest: DailyDigest) -> MediaArtifact:
        schema = {
            "type": "object",
            "properties": {
                "script": {"type": "string"},
            },
            "required": ["script"],
        }
        script_text = digest.final_text
        try:
            script_payload = self._llm_port.chat_structured(
                model=self._config.chat_model,
                messages=[
                    {
                        "role": "system",
                        "content": f"{self._config.script_prompt} Responda em JSON.",
                    },
                    {
                        "role": "user",
                        "content": digest.final_text,
                    },
                ],
                json_schema=schema,
            )
            script_text = str(script_payload.get("script", "")).strip() or digest.final_text
        except Exception as exc:
            self._logger.warning(
                "failed to generate podcast script with llm, using digest text",
                extra={"run_id": run_id, "error": str(exc)},
            )

        if len(script_text.strip()) < 120:
            script_text = self._build_fallback_script(digest)

        script_text = self._sanitize_for_tts(script_text)
        if len(script_text) < 80:
            script_text = self._sanitize_for_tts(self._build_fallback_script(digest))

        output_path = self._build_output_path(digest)
        rendered_path = self._tts_port.synthesize(script_text=script_text, output_path=output_path)

        checksum = hashlib.sha256(rendered_path.read_bytes()).hexdigest()
        artifact = MediaArtifact(run_id=run_id, type="audio", path=rendered_path, checksum=checksum)

        self._logger.info("synthesized podcast", extra={"run_id": run_id, "path": str(rendered_path)})
        return artifact
