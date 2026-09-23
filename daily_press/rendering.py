"""Print-first HTML and PDF rendering for Daily Press editions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from playwright.sync_api import sync_playwright


DEFAULT_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
DEFAULT_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class Renderer:
    """Render an edition to HTML and a US Letter PDF using Chromium."""

    def __init__(
        self,
        template_dir: Path | str = DEFAULT_TEMPLATE_DIR,
        static_dir: Path | str = DEFAULT_STATIC_DIR,
    ) -> None:
        self.template_dir = Path(template_dir)
        self.static_dir = Path(static_dir)
        self.environment = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=select_autoescape(["html", "xml"]),
            undefined=StrictUndefined,
        )
        self.template = self.environment.get_template("edition.html")
        self.css = (self.static_dir / "edition.css").read_text(encoding="utf-8")

    def render_html(self, edition: Any) -> str:
        """Render a complete self-contained HTML edition."""
        return self.template.render(edition=edition, css=self.css)

    def render_pdf(self, edition: Any, output_dir: Path | str) -> Path:
        """Write HTML and a Chromium-generated US Letter PDF to ``output_dir``."""
        destination = Path(output_dir)
        destination.mkdir(parents=True, exist_ok=True)
        html_path = destination / "edition.html"
        pdf_path = destination / "daily-press.pdf"
        html_path.write_text(self.render_html(edition), encoding="utf-8")

        browser = None
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch()
                page = browser.new_page()
                page.set_content(html_path.read_text(encoding="utf-8"), wait_until="load")
                page.pdf(
                    path=str(pdf_path),
                    format="Letter",
                    print_background=True,
                )
            finally:
                if browser is not None:
                    browser.close()
        return pdf_path
