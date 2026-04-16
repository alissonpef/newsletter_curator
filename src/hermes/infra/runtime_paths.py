from pathlib import Path


class RuntimePathProvider:
    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root

    def ensure_runtime_dirs(
        self,
        *,
        state_sqlite_path: Path,
        state_checkpoints_path: Path,
        vector_persist_path: Path,
        pdf_output_dir: Path,
        audio_output_dir: Path,
    ) -> None:
        runtime_paths = (
            self._project_root / "data/raw_email",
            self._project_root / "data/parsed_email",
            self._project_root / "data/chunks",
            vector_persist_path,
            state_sqlite_path.parent,
            state_checkpoints_path.parent,
            pdf_output_dir,
            audio_output_dir,
        )
        for path in runtime_paths:
            path.mkdir(parents=True, exist_ok=True)
