from datetime import datetime, timezone
from html import unescape
import re
from typing import Iterator

import feedparser
import httpx

from daily_press.collectors import CollectorError
from daily_press.models import ContentItem, Source


REQUEST_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
USER_AGENT = "Daily Press/0.1 (+https://daily-press.local)"


def collect_rss(source: Source, *, client: httpx.Client | None = None) -> list[ContentItem]:
    """Fetch one RSS or Atom source and normalize its entries."""
    owns_client = client is None
    http_client = client or httpx.Client()
    try:
        response = http_client.get(
            source.url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise CollectorError(source.name, str(error)) from error
    finally:
        if owns_client:
            http_client.close()

    parsed = feedparser.parse(response.content)
    if parsed.bozo and not parsed.entries:
        raise CollectorError(source.name, str(parsed.bozo_exception))

    return list(_content_items(parsed.entries, source))


def _content_items(entries: list[feedparser.FeedParserDict], source: Source) -> Iterator[ContentItem]:
    for entry in entries:
        title = _normalize_text(entry.get("title", ""))
        url = entry.get("link", "")
        if not title or not url:
            continue
        published_at = _published_at(entry.get("published_parsed") or entry.get("updated_parsed"))
        yield ContentItem(
            source=source.name,
            section=source.section,
            title=title,
            url=url,
            summary=_normalize_text(entry.get("summary", entry.get("description", ""))),
            published_at=published_at,
        )


def _normalize_text(value: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]*>", " ", value)).split())


def _published_at(value: object) -> datetime | None:
    if value is None:
        return None
    return datetime(*value[:6], tzinfo=timezone.utc)
