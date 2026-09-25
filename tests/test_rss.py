from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from daily_press.collectors import CollectorError
from daily_press.collectors.rss import collect_rss
from daily_press.models import Source


FIXTURES = Path(__file__).parent / "fixtures"


def test_collect_rss_normalizes_feed_entries_into_content_items() -> None:
    source = Source(
        name="Example Wire",
        url="https://feeds.example.test/latest.xml",
        section="aerospace-defense",
    )
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=(FIXTURES / "rss.xml").read_bytes())
        )
    )

    items = collect_rss(source, client=client)

    assert [(item.source, item.section, item.title, item.url, item.summary, item.published_at) for item in items] == [
        (
            "Example Wire",
            "aerospace-defense",
            "Orbital test reaches its target",
            "https://example.test/story/orbital-test?utm_source=rss",
            "A successful flight test.",
            datetime(2026, 9, 19, 13, 30, tzinfo=timezone.utc),
        ),
        (
            "Example Wire",
            "aerospace-defense",
            "Second story without a date",
            "https://example.test/story/second",
            "Short briefing.",
            None,
        ),
    ]


def test_collect_rss_wraps_http_failures_as_collector_errors() -> None:
    source = Source(name="Example Wire", url="https://feeds.example.test/latest.xml", section="top")
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(503, request=request))
    )

    with pytest.raises(CollectorError, match="Example Wire"):
        collect_rss(source, client=client)


def test_collect_rss_follows_redirects() -> None:
    source = Source(name="Example Wire", url="https://feeds.example.test/latest.xml", section="top")
    redirect_url = "https://feeds.example.test/current.xml"

    def respond(request: httpx.Request) -> httpx.Response:
        if str(request.url) == source.url:
            return httpx.Response(301, headers={"Location": redirect_url}, request=request)
        return httpx.Response(200, content=(FIXTURES / "rss.xml").read_bytes(), request=request)

    client = httpx.Client(transport=httpx.MockTransport(respond))

    assert [item.title for item in collect_rss(source, client=client)] == [
        "Orbital test reaches its target",
        "Second story without a date",
    ]
