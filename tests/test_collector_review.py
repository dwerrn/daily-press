from pathlib import Path

import feedparser
import httpx
import pytest

from daily_press.collectors import CollectorError
from daily_press.collectors.rss import MAX_CONTENT_ITEMS, MAX_RESPONSE_BYTES, collect_rss
from daily_press.collectors.weather import collect_weather
from daily_press.config import load_sources
from daily_press.models import Source


FIXTURES = Path(__file__).parent / "fixtures"
SOURCE = Source(name="Example Wire", url="https://feeds.example.test/latest.xml", section="top")


def _client(content: bytes = b"feed") -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=content))
    )


def test_collect_rss_rejects_html_without_a_feed_version() -> None:
    with pytest.raises(CollectorError, match="Example Wire"):
        collect_rss(SOURCE, client=_client((FIXTURES / "not-a-feed.html").read_bytes()))


def test_collect_rss_skips_entries_with_malformed_title_summary_or_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parsed = feedparser.FeedParserDict(
        version="rss20",
        bozo=False,
        entries=[
            feedparser.FeedParserDict(title={"not": "text"}, link="https://example.test/title"),
            feedparser.FeedParserDict(
                title="Bad summary", summary={"not": "text"}, link="https://example.test/summary"
            ),
            feedparser.FeedParserDict(
                title="Bad date", link="https://example.test/date", published_parsed="not-a-date"
            ),
            feedparser.FeedParserDict(title="Valid entry", link="https://example.test/valid"),
        ],
    )
    monkeypatch.setattr("daily_press.collectors.rss.feedparser.parse", lambda content: parsed)

    items = collect_rss(SOURCE, client=_client())

    assert [item.title for item in items] == ["Valid entry"]


def test_collect_rss_rejects_a_response_larger_than_the_body_limit() -> None:
    with pytest.raises(CollectorError, match="Example Wire"):
        collect_rss(SOURCE, client=_client(b"x" * (MAX_RESPONSE_BYTES + 1)))


def test_collect_rss_caps_normalized_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    entries = [
        feedparser.FeedParserDict(title=f"Entry {index}", link=f"https://example.test/{index}")
        for index in range(MAX_CONTENT_ITEMS + 1)
    ]
    parsed = feedparser.FeedParserDict(version="rss20", bozo=False, entries=entries)
    monkeypatch.setattr("daily_press.collectors.rss.feedparser.parse", lambda content: parsed)

    items = collect_rss(SOURCE, client=_client())

    assert len(items) == MAX_CONTENT_ITEMS
    assert items[-1].title == f"Entry {MAX_CONTENT_ITEMS - 1}"


def test_collect_weather_forwards_the_requested_timezone() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json={
                "current": {"temperature_2m": 16.4, "weather_code": 2},
                "daily": {
                    "temperature_2m_max": [23.7],
                    "temperature_2m_min": [15.1],
                    "precipitation_probability_max": [35],
                },
            },
        )

    collect_weather(
        40.7128,
        -74.0060,
        timezone="America/New_York",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert captured_request is not None
    assert captured_request.url.params["timezone"] == "America/New_York"


def test_default_sources_exclude_the_ap_html_page_and_use_defense_ones_feed() -> None:
    sources = {source.name: source.url for source in load_sources()}

    assert "AP" not in sources
    assert sources["Defense One"] == "https://www.defenseone.com/rss/all/"
