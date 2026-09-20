"""SQLite persistence for collected stories and generated editions."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, MetaData, String, Table, create_engine, event, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection

from daily_press.models import ContentItem


metadata = MetaData()

sources = Table(
    "sources",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False, unique=True),
)
stories = Table(
    "stories",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("canonical_url_hash", String(64), nullable=False, unique=True),
    Column("canonical_url", String, nullable=False),
    Column("source_id", ForeignKey("sources.id"), nullable=False),
    Column("title", String, nullable=False),
    Column("url", String, nullable=False),
    Column("summary", String, nullable=False),
    Column("published_at", DateTime(timezone=True)),
    Column("section", String, nullable=False),
)
editions = Table(
    "editions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("edition_date", Date, nullable=False, unique=True),
)
edition_items = Table(
    "edition_items",
    metadata,
    Column("edition_id", ForeignKey("editions.id"), primary_key=True),
    Column("story_id", ForeignKey("stories.id"), primary_key=True),
)
runs = Table(
    "runs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("status", String, nullable=False),
)


class StoryRepository:
    """A small, synchronous repository for the daily generation workflow."""

    def __init__(self, database: str | Path) -> None:
        self.engine = create_engine(_database_url(database))
        event.listen(self.engine, "connect", _enable_foreign_keys)
        metadata.create_all(self.engine)

    def record(self, item: ContentItem) -> int:
        """Store a story once, keyed by its normalized canonical URL."""
        with self.engine.begin() as connection:
            return self._record(connection, item)

    def record_printed(self, item: ContentItem, edition_date: date) -> None:
        """Associate a story with the dated edition, safely on repeated runs."""
        with self.engine.begin() as connection:
            story_id = self._record(connection, item)
            connection.execute(
                sqlite_insert(editions)
                .values(edition_date=edition_date)
                .on_conflict_do_nothing(index_elements=[editions.c.edition_date])
            )
            edition_id = connection.scalar(
                select(editions.c.id).where(editions.c.edition_date == edition_date)
            )
            if edition_id is None:
                raise RuntimeError("edition insertion did not produce a row")
            connection.execute(
                sqlite_insert(edition_items)
                .values(edition_id=edition_id, story_id=story_id)
                .on_conflict_do_nothing(
                    index_elements=[edition_items.c.edition_id, edition_items.c.story_id]
                )
            )

    def _record(self, connection: Connection, item: ContentItem) -> int:
        canonical_url = item.canonical_url
        url_hash = sha256(canonical_url.encode()).hexdigest()
        connection.execute(
            sqlite_insert(sources)
            .values(name=item.source)
            .on_conflict_do_nothing(index_elements=[sources.c.name])
        )
        source_id = connection.scalar(select(sources.c.id).where(sources.c.name == item.source))
        if source_id is None:
            raise RuntimeError("source insertion did not produce a row")
        connection.execute(
            sqlite_insert(stories)
            .values(
                canonical_url_hash=url_hash,
                canonical_url=canonical_url,
                source_id=source_id,
                title=item.title,
                url=canonical_url,
                summary=item.summary,
                published_at=_as_utc(item.published_at),
                section=item.section,
            )
            .on_conflict_do_nothing(index_elements=[stories.c.canonical_url_hash])
        )
        story_id = connection.scalar(
            select(stories.c.id).where(stories.c.canonical_url_hash == url_hash)
        )
        if story_id is None:
            raise RuntimeError("story insertion did not produce a row")
        return story_id

    def was_printed_within(self, item: ContentItem, edition_date: date, days: int = 7) -> bool:
        """Return whether the story appeared in the preceding inclusive window."""
        url_hash = sha256(item.canonical_url.encode()).hexdigest()
        earliest_date = edition_date - timedelta(days=days)
        with self.engine.connect() as connection:
            return (
                connection.scalar(
                    select(edition_items.c.story_id)
                    .join(stories, edition_items.c.story_id == stories.c.id)
                    .join(editions, edition_items.c.edition_id == editions.c.id)
                    .where(
                        stories.c.canonical_url_hash == url_hash,
                        editions.c.edition_date >= earliest_date,
                        editions.c.edition_date <= edition_date,
                    )
                    .limit(1)
                )
                is not None
            )

    def stories(self) -> list[ContentItem]:
        """Return stored stories in insertion order, for archival and tests."""
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(
                    sources.c.name,
                    stories.c.title,
                    stories.c.url,
                    stories.c.summary,
                    stories.c.published_at,
                    stories.c.section,
                )
                .join(sources, stories.c.source_id == sources.c.id)
                .order_by(stories.c.id)
            )
            return [
                ContentItem(
                    source=row.name,
                    title=row.title,
                    url=row.url,
                    summary=row.summary,
                    published_at=_as_utc(row.published_at),
                    section=row.section,
                )
                for row in rows
            ]


def _database_url(database: str | Path) -> str:
    if isinstance(database, Path):
        return f"sqlite:///{database}"
    return database if "://" in database else f"sqlite:///{database}"


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _enable_foreign_keys(dbapi_connection, connection_record) -> None:
    del connection_record
    dbapi_connection.execute("PRAGMA foreign_keys=ON")
