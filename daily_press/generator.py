"""The shared, locked Daily Press generation workflow."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TypeAlias

from filelock import FileLock, Timeout

from daily_press.collectors.rss import collect_rss
from daily_press.collectors.weather import collect_weather
from daily_press.config import Settings
from daily_press.db import StoryRepository
from daily_press.editorial import pre_rank
from daily_press.models import ContentItem, Edition, Source, WeatherForecast
from daily_press.openai_editor import OpenAIEditor
from daily_press.rendering import Renderer


EditorialKeywords: TypeAlias = Iterable[str]
RssCollector: TypeAlias = Callable[[Source], list[ContentItem]]
WeatherCollector: TypeAlias = Callable[[float, float, str], WeatherForecast]

DEFAULT_EDITORIAL_KEYWORDS = (
    "consequential",
    "aerospace",
    "defense",
    "engineering",
    "technology",
)


class GenerationInProgress(RuntimeError):
    """Raised when another timer or manual run owns the generation lock."""


@dataclass(frozen=True)
class GenerationResult:
    edition_date: date
    status: str
    html_path: Path
    pdf_path: Path
    source_errors: tuple[str, ...] = ()
    editorial_mode: str = "deterministic"

    def public_dict(self) -> dict[str, object]:
        return {
            "edition_date": self.edition_date.isoformat(),
            "status": self.status,
            "html_path": str(self.html_path),
            "pdf_path": str(self.pdf_path),
            "source_errors": list(self.source_errors),
            "editorial_mode": self.editorial_mode,
        }

    def api_dict(self) -> dict[str, object]:
        """Return an HTTP-safe summary without exposing local filesystem paths."""
        edition = self.edition_date.isoformat()
        return {
            "edition_date": edition,
            "status": self.status,
            "html_url": f"/editions/{edition}",
            "pdf_url": f"/editions/{edition}/pdf",
            "source_errors": list(self.source_errors),
            "editorial_mode": self.editorial_mode,
        }


class EditionGenerator:
    """Collect, select, render, and archive one dated edition."""

    def __init__(
        self,
        settings: Settings,
        *,
        repository: StoryRepository | None = None,
        renderer: Renderer | None = None,
        editor: OpenAIEditor | None = None,
        rss_collector: RssCollector = collect_rss,
        weather_collector: WeatherCollector = collect_weather,
        editorial_keywords: EditorialKeywords = DEFAULT_EDITORIAL_KEYWORDS,
        lock_path: Path | str | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository or StoryRepository(settings.database_url)
        self.renderer = renderer or Renderer()
        self.editor = editor or OpenAIEditor(api_key=settings.openai_api_key)
        self.rss_collector = rss_collector
        self.weather_collector = weather_collector
        self.editorial_keywords = tuple(editorial_keywords)
        self.archive_dir = Path(settings.archive_dir)
        self.lock_path = Path(lock_path or Path(settings.data_dir) / "generation.lock")

    async def generate(self, edition_date: date | None = None) -> GenerationResult:
        """Generate an edition, preserving it even when individual sources fail."""
        target_date = edition_date or date.today()
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with FileLock(str(self.lock_path), timeout=0):
                return await self._generate_locked(target_date)
        except Timeout as error:
            raise GenerationInProgress("another generation is already running") from error

    async def _generate_locked(self, edition_date: date) -> GenerationResult:
        run_id = self.repository.start_run()
        source_errors: list[str] = []
        try:
            collected, weather, source_errors = await self._collect()
            for item in collected:
                self.repository.record(item)

            candidates = pre_rank(
                collected,
                self.repository,
                edition_date,
                self.editorial_keywords,
            )
            selection = self.editor.select(candidates, edition_date)
            edition = Edition(
                edition_date=edition_date,
                location_name=self.settings.location_name,
                weather=weather,
                top_stories=selection.top_stories,
                radar_stories=selection.radar_stories,
            )
            output_dir = self.archive_dir / edition_date.isoformat()
            pdf_path = self.renderer.render_pdf(edition, output_dir)
            html_path = output_dir / "edition.html"
            for story in (*selection.top_stories, *selection.radar_stories):
                self.repository.record_printed(candidates[story.candidate_index], edition_date)

            status = "partial" if source_errors else "complete"
            self.repository.finish_run(run_id, status)
            return GenerationResult(
                edition_date=edition_date,
                status=status,
                html_path=html_path,
                pdf_path=pdf_path,
                source_errors=tuple(source_errors),
                editorial_mode=selection.mode,
            )
        except Exception:
            self.repository.finish_run(run_id, "failed")
            raise

    async def _collect(self) -> tuple[list[ContentItem], WeatherForecast | None, list[str]]:
        jobs = [self._collect_source(source) for source in self.settings.sources]
        jobs.append(
            self._collect_weather()
        )
        results = await asyncio.gather(*jobs, return_exceptions=True)
        collected: list[ContentItem] = []
        errors: list[str] = []
        for source, result in zip(self.settings.sources, results[:-1], strict=True):
            if isinstance(result, Exception):
                errors.append(f"{source.name}: {type(result).__name__}")
                continue
            collected.extend(result)

        weather_result = results[-1]
        weather: WeatherForecast | None = None
        if isinstance(weather_result, Exception):
            errors.append(f"weather: {type(weather_result).__name__}")
        else:
            weather = weather_result
        return collected, weather, errors

    async def _collect_source(self, source: Source) -> list[ContentItem]:
        return self.rss_collector(source)

    async def _collect_weather(self) -> WeatherForecast:
        return self.weather_collector(
            self.settings.latitude,
            self.settings.longitude,
            self.settings.timezone,
        )
