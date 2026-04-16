from pathlib import Path
import logging
import logging.config

import yaml


class _RunIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "run_id"):
            record.run_id = "-"
        return True


def configure_logging(config_path: Path | str) -> None:
    path = Path(config_path)

    if path.exists():
        with path.open("r", encoding="utf-8") as stream:
            payload = yaml.safe_load(stream) or {}
        logging.config.dictConfig(payload)
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s run_id=%(run_id)s %(message)s",
        )

    run_id_filter = _RunIdFilter()
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(run_id_filter)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
