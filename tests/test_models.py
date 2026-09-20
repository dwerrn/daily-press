from datetime import datetime

import pytest
from pydantic import ValidationError

from daily_press.models import ContentItem, Source


def test_canonical_url_removes_tracking_parameters_and_fragments() -> None:
    item = ContentItem(
        source="Reuters",
        title="Example story",
        url="https://www.reuters.com/world/example?b=2&utm_source=newsletter&a=1&utm_campaign=morning#details",
    )

    assert item.canonical_url == "https://www.reuters.com/world/example?a=1&b=2"


def test_content_item_is_immutable() -> None:
    item = ContentItem(
        source="AP",
        title="Example story",
        url="https://apnews.com/article/example",
        published_at=datetime(2026, 9, 19),
    )

    with pytest.raises(ValidationError):
        item.title = "Updated story"


def test_canonical_url_normalizes_authority_and_preserves_repeated_key_order() -> None:
    item = ContentItem(
        source="Reuters",
        title="Example story",
        url="HTTPS://NEWS.EXAMPLE.COM:443/story?tag=z&b=2&utm_source=feed&tag=a&a=1#summary",
    )

    assert item.canonical_url == "https://news.example.com/story?a=1&b=2&tag=z&tag=a"


def test_source_is_immutable_and_requires_https() -> None:
    source = Source(name="Reuters", url="https://www.reuters.com/", section="top")

    with pytest.raises(ValidationError):
        source.name = "Updated"
    with pytest.raises(ValidationError):
        Source(name="Reuters", url="http://www.reuters.com/", section="top")
@pytest.mark.parametrize(
    "url",
    [
        "https://example.com:invalid/feed",
        "https://exa mple.com/feed",
    ],
)
def test_source_rejects_malformed_https_urls(url: str) -> None:
    with pytest.raises(ValidationError):
        Source(name="Reuters", url=url, section="top")
