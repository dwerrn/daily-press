import asyncio
from datetime import date
from pathlib import Path

from daily_press.config import Settings
from daily_press.db import StoryRepository
from daily_press.generator import EditionGenerator
from daily_press.models import ContentItem, Source, WeatherForecast


class FakeRenderer:
    def render_pdf(self, edition, output_dir: Path) -> Path:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise AssertionError("sync renderer must run outside the event loop")
        del edition
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "edition.html").write_text("<html>edition</html>", encoding="utf-8")
        pdf_path = output_dir / "daily-press.pdf"
        pdf_path.write_bytes(b"%PDF-fake")
        return pdf_path


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        location_name="New York, United States",
        latitude=40.7,
        longitude=-74.0,
        timezone="America/New_York",
        data_dir=str(tmp_path / "data"),
        archive_dir=str(tmp_path / "archive"),
        database_url=str(tmp_path / "daily-press.db"),
        sources=(
            Source(name="Good Wire", url="https://good.example/feed", section="top"),
            Source(name="Broken Wire", url="https://broken.example/feed", section="top"),
        ),
    )


def test_generation_archives_partial_edition_when_one_source_fails(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    def rss(source: Source) -> list[ContentItem]:
        if source.name == "Broken Wire":
            raise RuntimeError("fixture failure")
        return [
            ContentItem(
                source=source.name,
                title="A useful morning story",
                url="https://good.example/story",
                summary="A source-grounded excerpt.",
                section=source.section,
            )
        ]

    def weather(latitude: float, longitude: float, timezone: str) -> WeatherForecast:
        del latitude, longitude, timezone
        return WeatherForecast(
            current_temperature_c=16.0,
            high_temperature_c=22.0,
            low_temperature_c=14.0,
            precipitation_probability=20,
            condition="clear sky",
        )

    generator = EditionGenerator(
        settings,
        repository=StoryRepository(tmp_path / "daily-press.db"),
        renderer=FakeRenderer(),
        rss_collector=rss,
        weather_collector=weather,
    )

    result = asyncio.run(generator.generate(date(2026, 9, 20)))

    assert result.status == "partial"
    assert result.pdf_path.exists()
    assert result.source_errors == ("Broken Wire: RuntimeError",)
    assert result.editorial_mode == "deterministic"
    assert result.pdf_path.parent == tmp_path / "archive" / "2026-09-20"
