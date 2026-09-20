"""Deterministic editorial candidate selection before AI-assisted editing."""

from collections.abc import Iterable
from datetime import date, timezone

from daily_press.db import StoryRepository
from daily_press.models import ContentItem


MAX_CANDIDATES = 12


def pre_rank(
    items: Iterable[ContentItem],
    repository: StoryRepository,
    edition_date: date,
    editorial_keywords: Iterable[str],
) -> list[ContentItem]:
    """Return the best unprinted items with a stable, transparent ordering."""
    keywords = tuple(keyword.casefold() for keyword in editorial_keywords if keyword.strip())
    candidates: list[tuple[int, int, ContentItem]] = []
    seen_urls: set[str] = set()
    for position, item in enumerate(items):
        if item.canonical_url in seen_urls or repository.was_printed_within(item, edition_date):
            continue
        seen_urls.add(item.canonical_url)
        candidates.append((-_score(item, edition_date, keywords), position, item))
    candidates.sort(key=lambda candidate: (candidate[0], candidate[1]))
    return [item for _, _, item in candidates[:MAX_CANDIDATES]]


def _score(item: ContentItem, edition_date: date, keywords: tuple[str, ...]) -> int:
    recency = 0
    if item.published_at is not None:
        published_date = item.published_at.astimezone(timezone.utc).date()
        recency = max(0, 14 - max(0, (edition_date - published_date).days))
    searchable_text = " ".join((item.source, item.section, item.title, item.summary)).casefold()
    relevance = sum(keyword in searchable_text for keyword in keywords)
    return recency + relevance * 20
