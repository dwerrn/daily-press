from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from daily_press.db import StoryRepository, edition_items
from daily_press.editorial import pre_rank
from daily_press.models import ContentItem, Source


def _item(number: int, **overrides: object) -> ContentItem:
    values: dict[str, object] = {
        "source": "General Wire",
        "source_quality": 0,
        "section": "top",
        "title": f"General story {number}",
        "url": f"https://example.test/story-{number}",
        "summary": "General news update.",
        "published_at": datetime(2026, 9, 18, 12, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return ContentItem(**values)


def test_source_quality_weight_is_configurable_and_carried_by_content_items() -> None:
    source = Source(
        name="Trusted Wire",
        url="https://feeds.example.test/latest.xml",
        section="top",
        quality_weight=8,
    )
    item = _item(1, source_quality=source.quality_weight)

    assert source.quality_weight == 8
    assert item.source_quality == 8


def test_pre_rank_prefers_a_higher_quality_source_when_other_signals_tie(tmp_path) -> None:
    repository = StoryRepository(tmp_path / "daily-press.db")
    low_quality = _item(1, source="Low Quality", source_quality=0, title="Local transit update")
    high_quality = _item(2, source="Trusted Wire", source_quality=8, title="Lunar propulsion briefing")

    candidates = pre_rank([low_quality, high_quality], repository, date(2026, 9, 19), [])

    assert candidates == [high_quality, low_quality]


def test_pre_rank_deduplicates_similar_titles_from_different_sources(tmp_path) -> None:
    repository = StoryRepository(tmp_path / "daily-press.db")
    first = _item(1, source="Wire One", title="NASA launches new moon mission")
    better = _item(
        2,
        source="Wire Two",
        source_quality=4,
        title="NASA launches moon mission",
    )

    candidates = pre_rank([first, better], repository, date(2026, 9, 19), [])

    assert candidates == [better]


def test_record_printed_is_idempotent_for_repeated_calls(tmp_path) -> None:
    repository = StoryRepository(tmp_path / "daily-press.db")
    item = _item(1)

    repository.record_printed(item, date(2026, 9, 19))
    repository.record_printed(item, date(2026, 9, 19))

    with repository.engine.connect() as connection:
        count = connection.scalar(select(func.count()).select_from(edition_items))
    assert count == 1


def test_repository_connections_enforce_foreign_key_constraints(tmp_path) -> None:
    repository = StoryRepository(tmp_path / "daily-press.db")

    with pytest.raises(IntegrityError):
        with repository.engine.begin() as connection:
            connection.execute(edition_items.insert().values(edition_id=999, story_id=999))


def test_content_item_requires_an_absolute_https_article_url() -> None:
    with pytest.raises(ValidationError):
        _item(1, url="/only-a-path")
    with pytest.raises(ValidationError):
        _item(2, url="http://example.test/story")


def test_content_item_normalizes_root_urls_and_naive_dates_at_model_ingress() -> None:
    item = _item(1, url="https://EXAMPLE.test", published_at=datetime(2026, 9, 19, 8, 30))

    assert item.canonical_url == "https://example.test/"
    assert item.published_at == datetime(2026, 9, 19, 8, 30, tzinfo=timezone.utc)
