from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class Bookmark:
    """A stored bookmark record."""

    id: int
    url: str
    title: str
    tags: list[str]
    desc: str | None
    created_at: str


@dataclass
class BookmarkCreate:
    """Input data for creating a bookmark."""

    url: str
    title: str
    tags: list[str]
    desc: str | None


@dataclass
class BookmarkUpdate:
    """Input data for updating a bookmark."""

    title: str | None = None
    tags: list[str] | None = None
    desc: str | None = None


def normalize_tags(tags: list[str] | None) -> list[str]:
    """Return cleaned tags preserving order and removing duplicates."""

    if tags is None:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        value = tag.strip()
        if not value:
            continue
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(value)
    return cleaned


def tags_to_db(tags: list[str]) -> str:
    """Serialize tags for SQLite storage."""

    return ",".join(normalize_tags(tags))


def tags_from_db(tags: str | None) -> list[str]:
    """Deserialize SQLite tag storage into a Python list."""

    if not tags:
        return []
    return normalize_tags(tags.split(","))


def row_to_bookmark(row: Any) -> Bookmark:
    """Convert a SQLite row into a Bookmark instance."""

    return Bookmark(
        id=int(row["id"]),
        url=str(row["url"]),
        title=str(row["title"]),
        tags=tags_from_db(row["tags"]),
        desc=row["description"],
        created_at=str(row["created_at"]),
    )


def utcnow_iso() -> str:
    """Return an ISO 8601 UTC timestamp without microseconds."""

    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
