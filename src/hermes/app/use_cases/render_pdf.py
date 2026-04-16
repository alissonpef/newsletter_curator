import hashlib

from ...app.runtime_config import RenderPdfConfig
from ...core.entities import DailyDigest, MediaArtifact
from ...infra.artifact_naming import ArtifactNamingService
from ...ports.pdf_port import PdfPort


class RenderPdfUseCase:
    def __init__(
        self,
        pdf_port: PdfPort,
        logger,
        config: RenderPdfConfig,
        artifact_naming: ArtifactNamingService | None = None,
    ) -> None:
        self._pdf_port = pdf_port
        self._logger = logger
        self._config = config
        self._artifact_naming = artifact_naming or ArtifactNamingService()

    def _build_output_path(self, digest: DailyDigest):
        base_hint = digest.themes[0] if digest.themes else "newsletter"
        return self._artifact_naming.build_versioned_path(
            output_dir=self._config.output_dir,
            date_ref=digest.date_ref,
            hint=base_hint,
            extension="pdf",
            default_hint="newsletter",
        )

    def execute(self, run_id: str, digest: DailyDigest) -> MediaArtifact:
        output_path = self._build_output_path(digest)
        rendered_path = self._pdf_port.render(
            template_name=self._config.template_name,
            context={"digest": digest},
            output_path=output_path,
        )

        checksum = hashlib.sha256(rendered_path.read_bytes()).hexdigest()
        artifact = MediaArtifact(run_id=run_id, type="pdf", path=rendered_path, checksum=checksum)

        self._logger.info("rendered pdf", extra={"run_id": run_id, "path": str(rendered_path)})
        return artifact
