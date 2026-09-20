from datetime import datetime, timezone
from html import unescape
import re
from itertools import islice

import feedparser
import httpx

from daily_press.collectors import CollectorError
from daily_press.models import ContentItem, Source


REQUEST_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
USER_AGENT = "Daily Press/0.1 (+https://daily-press.local)"
MAX_RESPONSE_BYTES = 1_000_000
MAX_CONTENT_ITEMS = 100


def collect_rss(source: Source, *, client: httpx.Client | None = None) -> list[ContentItem]:
    """Fetch one RSS or Atom source and normalize its entries."""
    owns_client = client is None
    http_client = client or httpx.Client()
    try:
        response_content = _fetch_response_content(http_client, source)
    except httpx.HTTPError as error:
        raise CollectorError(source.name, str(error)) from error
    finally:
        if owns_client:
            http_client.close()

    parsed = feedparser.parse(response_content)
    if not parsed.get("version"):
        raise CollectorError(source.name, "response is not an RSS or Atom feed")
    if parsed.bozo and not parsed.entries:
        raise CollectorError(source.name, str(parsed.bozo_exception))

    return list(islice(_content_items(parsed.entries, source), MAX_CONTENT_ITEMS))


def _fetch_response_content(client: httpx.Client, source: Source) -> bytes:
    with client.stream(
        "GET",
        source.url,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
    ) as response:
        response.raise_for_status()
        chunks: list[bytes] = []
        response_size = 0
        for chunk in response.iter_bytes():
            response_size += len(chunk)
            if response_size > MAX_RESPONSE_BYTES:
                raise CollectorError(source.name, f"response exceeds {MAX_RESPONSE_BYTES} byte limit")
            chunks.append(chunk)
    return b"".join(chunks)


def _content_items(entries: list[feedparser.FeedParserDict], source: Source):
    for entry in entries:
        try:
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
        except (AttributeError, IndexError, TypeError, ValueError):
            continue


def _normalize_text(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("feed text fields must be strings")
    return " ".join(unescape(re.sub(r"<[^>]*>", " ", value)).split())


def _published_at(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, tuple) or len(value) < 6:
        raise ValueError("feed publication date must be a parsed timestamp")
    return datetime(*value[:6], tzinfo=timezone.utc)
