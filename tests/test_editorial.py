from datetime import date, datetime, timedelta, timezone

from daily_press.db import StoryRepository
from daily_press.editorial import pre_rank
from daily_press.models import ContentItem


EDITION_DATE = date(2026, 9, 19)


def _item(number: int, **overrides: object) -> ContentItem:
    values: dict[str, object] = {
        "source": "General Wire",
        "section": "top",
        "title": f"General story {number}",
        "url": f"https://example.test/story-{number}",
        "summary": "General news update.",
        "published_at": datetime(2026, 9, 18, 12, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return ContentItem(**values)


def test_pre_rank_prefers_newer_interest_matching_stories(tmp_path) -> None:
    repository = StoryRepository(tmp_path / "daily-press.db")
    older_general = _item(1, published_at=datetime(2026, 9, 16, 12, tzinfo=timezone.utc))
    relevant_fresh = _item(
        2,
        title="New lunar propulsion test",
        section="aerospace-defense",
        published_at=datetime(2026, 9, 18, 18, tzinfo=timezone.utc),
    )

    candidates = pre_rank(
        [older_general, relevant_fresh], repository, EDITION_DATE, ["lunar", "propulsion"]
    )

    assert candidates == [relevant_fresh, older_general]


def test_pre_rank_suppresses_stories_printed_in_the_previous_week(tmp_path) -> None:
    repository = StoryRepository(tmp_path / "daily-press.db")
    printed = _item(1)
    new_story = _item(2)
    repository.record_printed(printed, EDITION_DATE - timedelta(days=2))

    candidates = pre_rank([printed, new_story], repository, EDITION_DATE, [])

    assert candidates == [new_story]


def test_pre_rank_returns_at_most_twelve_candidates_in_stable_order(tmp_path) -> None:
    repository = StoryRepository(tmp_path / "daily-press.db")
    items = [_item(number) for number in range(20)]

    candidates = pre_rank(items, repository, EDITION_DATE, [])

    assert [item.title for item in candidates] == [f"General story {number}" for number in range(12)]
