from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML


class WeasyprintRenderer:
    def __init__(self, template_dir: Path) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(("html", "xml", "j2")),
        )
        self._template_dir = template_dir

    def render(self, template_name: str, context: dict[str, Any], output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        template = self._env.get_template(template_name)
        html = template.render(**context)
        HTML(string=html, base_url=str(self._template_dir)).write_pdf(str(output_path))
        return output_path
