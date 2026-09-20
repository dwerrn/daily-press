from datetime import date, datetime, timezone

from daily_press.db import StoryRepository
from daily_press.models import ContentItem


def _item(**overrides: object) -> ContentItem:
    values: dict[str, object] = {
        "source": "Reuters",
        "section": "top",
        "title": "Launch succeeds",
        "url": "https://example.test/launch?utm_source=rss",
        "summary": "A successful launch.",
        "published_at": datetime(2026, 9, 19, 12, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return ContentItem(**values)


def test_repository_persists_a_normalized_story(tmp_path) -> None:
    repository = StoryRepository(tmp_path / "daily-press.db")
    item = _item()

    repository.record(item)

    stored = repository.stories()
    assert len(stored) == 1
    assert stored[0].canonical_url == "https://example.test/launch"
    assert stored[0].title == item.title
    assert stored[0].published_at == item.published_at


def test_repository_insertion_is_idempotent_for_the_same_canonical_url(tmp_path) -> None:
    repository = StoryRepository(tmp_path / "daily-press.db")

    repository.record(_item())
    repository.record(_item(url="https://example.test/launch?utm_campaign=morning"))

    assert len(repository.stories()) == 1


def test_repository_tracks_when_a_story_was_printed(tmp_path) -> None:
    repository = StoryRepository(tmp_path / "daily-press.db")
    item = _item()
    printed_on = date(2026, 9, 19)

    repository.record_printed(item, printed_on)

    assert repository.was_printed_within(item, date(2026, 9, 25))
    assert not repository.was_printed_within(item, date(2026, 9, 27))
