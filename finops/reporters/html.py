from __future__ import annotations
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from finops.reporters.models import Report

_TEMPLATES_DIR = Path(__file__).parent / "templates"


class HtmlReporter:
    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=True,
        )

    def render(self, report: Report) -> str:
        template = self._env.get_template("report.html.j2")
        return template.render(report=report)
