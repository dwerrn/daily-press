"""Deterministic editorial candidate selection before AI-assisted editing."""

from collections.abc import Iterable
from datetime import date, timezone
import re

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

    selected: list[ContentItem] = []
    for _, _, item in candidates:
        if any(_titles_are_similar(item.title, selected_item.title) for selected_item in selected):
            continue
        selected.append(item)
        if len(selected) == MAX_CANDIDATES:
            break
    return selected


def _score(item: ContentItem, edition_date: date, keywords: tuple[str, ...]) -> int:
    recency = 0
    if item.published_at is not None:
        published_date = item.published_at.astimezone(timezone.utc).date()
        recency = max(0, 14 - max(0, (edition_date - published_date).days))
    searchable_text = " ".join((item.source, item.section, item.title, item.summary)).casefold()
    relevance = sum(keyword in searchable_text for keyword in keywords)
    return recency + relevance * 20 + item.source_quality


def _titles_are_similar(left: str, right: str) -> bool:
    normalized_left = _normalize_title(left)
    normalized_right = _normalize_title(right)
    if normalized_left == normalized_right:
        return True
    left_tokens = set(normalized_left.split())
    right_tokens = set(normalized_right.split())
    if not left_tokens or not right_tokens:
        return False
    token_similarity = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    return token_similarity >= 0.8


def _normalize_title(title: str) -> str:
    tokens = re.findall(r"[\w]+", title.casefold())
    return " ".join(token for token in tokens if token not in {"a", "an", "the"})
