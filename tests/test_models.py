from datetime import datetime

import pytest
from pydantic import ValidationError

from daily_press.models import ContentItem


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
