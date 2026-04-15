"""Bookmark data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Bookmark:
    """A single bookmark entry."""

    url: str
    title: str = ""
    tags: list[str] = field(default_factory=list)
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    id: int | None = None

    @property
    def tags_csv(self) -> str:
        """Return tags as comma-separated string for DB storage."""
        return ",".join(self.tags)

    @classmethod
    def from_row(cls, row: tuple[int, str, str, str, str, str]) -> Bookmark:
        """Create a Bookmark from a database row (id, url, title, tags, description, created_at)."""
        id_, url, title, tags_csv, description, created_at = row
        tags = [t.strip() for t in tags_csv.split(",") if t.strip()] if tags_csv else []
        return cls(
            id=id_,
            url=url,
            title=title,
            tags=tags,
            description=description,
            created_at=created_at,
        )
