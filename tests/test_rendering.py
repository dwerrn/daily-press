from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from daily_press.models import Edition, EditionStory, WeatherForecast
from daily_press.rendering import Renderer


TEMPLATES = Path(__file__).parents[1] / "templates"


def _story(index: int, source: str, section: str) -> EditionStory:
    return EditionStory(
        candidate_index=index,
        source=source,
        title=f"Story {index}",
        url=f"https://example.test/story-{index}",
        summary=f"A useful source-grounded summary for story {index}.",
        section=section,
    )


def _edition() -> Edition:
    return Edition(
        edition_date=date(2026, 9, 20),
        location_name="New York, United States",
        weather=WeatherForecast(
            current_temperature_c=16.4,
            high_temperature_c=23.7,
            low_temperature_c=15.1,
            precipitation_probability=35,
            condition="partly cloudy",
        ),
        top_stories=[
            _story(0, "Reuters", "top"),
            _story(1, "NASA", "aerospace-defense"),
            _story(2, "IEEE Spectrum", "engineering-technology"),
        ],
        radar_stories=[
            _story(3, "Defense One", "aerospace-defense"),
            _story(4, "The Register", "engineering-technology"),
        ],
    )


def test_renderer_inlines_story_and_weather_content() -> None:
    html = Renderer(template_dir=TEMPLATES).render_html(_edition())

    assert "THE DAILY PRESS" in html
    assert "Story 0" in html
    assert "partly cloudy" in html
    assert "@page" in html


def test_edition_story_rejects_non_https_links() -> None:
    with pytest.raises(ValidationError):
        EditionStory(
            candidate_index=0,
            source="Reuters",
            title="Unsafe story",
            url="javascript:alert(1)",
            summary="Unsafe link",
            section="top",
        )


def test_renderer_writes_letter_pdf(tmp_path: Path) -> None:
    pdf_path = Renderer(template_dir=TEMPLATES).render_pdf(_edition(), tmp_path)

    assert pdf_path == tmp_path / "daily-press.pdf"
    assert pdf_path.read_bytes().startswith(b"%PDF")
    assert (tmp_path / "edition.html").is_file()
