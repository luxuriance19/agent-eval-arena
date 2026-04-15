from __future__ import annotations

import sqlite3
from pathlib import Path

from bmk.models import Bookmark, BookmarkCreate, BookmarkUpdate, normalize_tags, row_to_bookmark, tags_to_db, utcnow_iso


SCHEMA = """
CREATE TABLE IF NOT EXISTS bookmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    description TEXT,
    created_at TEXT NOT NULL
)
"""


def connect_db(db_path: Path) -> sqlite3.Connection:
    """Return a SQLite connection configured for row access."""

    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: Path) -> None:
    """Create the bookmark database and schema if needed."""

    with connect_db(db_path) as connection:
        connection.execute(SCHEMA)
        connection.commit()


def duplicate_url_exists(db_path: Path, url: str) -> bool:
    """Return whether a bookmark with the same URL already exists."""

    with connect_db(db_path) as connection:
        row = connection.execute("SELECT 1 FROM bookmarks WHERE url = ?", (url,)).fetchone()
    return row is not None


class BookmarkDB:
    """SQLite-backed bookmark storage."""

    def __init__(self, path: Path) -> None:
        self.path = path
        init_db(path)

    def add_bookmark(self, bookmark: BookmarkCreate) -> Bookmark:
        """Insert a bookmark and return the stored record."""

        tags = normalize_tags(bookmark.tags)
        try:
            with connect_db(self.path) as connection:
                cursor = connection.execute(
                    "INSERT INTO bookmarks (url, title, tags, description, created_at) VALUES (?, ?, ?, ?, ?)",
                    (bookmark.url, bookmark.title, tags_to_db(tags), bookmark.desc, utcnow_iso()),
                )
                connection.commit()
                row = connection.execute("SELECT * FROM bookmarks WHERE id = ?", (cursor.lastrowid,)).fetchone()
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Bookmark for URL already exists: {bookmark.url}") from exc
        assert row is not None
        return row_to_bookmark(row)

    def list_bookmarks(self, tag: str | None = None, limit: int | None = None, sort: str = "date") -> list[Bookmark]:
        """Return bookmarks optionally filtered by tag."""

        sort_sql = "created_at DESC" if sort == "date" else "title COLLATE NOCASE ASC"
        query = "SELECT * FROM bookmarks"
        params: list[object] = []
        if tag:
            query += " WHERE tags LIKE ?"
            params.append(f"%{tag}%")
        query += f" ORDER BY {sort_sql}"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with connect_db(self.path) as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        bookmarks = [row_to_bookmark(row) for row in rows]
        if tag:
            lowered = tag.lower()
            bookmarks = [bookmark for bookmark in bookmarks if lowered in {value.lower() for value in bookmark.tags}]
        return bookmarks

    def get_bookmark(self, bookmark_id: int) -> Bookmark | None:
        """Return one bookmark by id."""

        with connect_db(self.path) as connection:
            row = connection.execute("SELECT * FROM bookmarks WHERE id = ?", (bookmark_id,)).fetchone()
        return row_to_bookmark(row) if row is not None else None

    def delete_bookmark(self, bookmark_id: int) -> bool:
        """Delete a bookmark by id."""

        with connect_db(self.path) as connection:
            cursor = connection.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
            connection.commit()
        return cursor.rowcount > 0

    def edit_bookmark(self, bookmark_id: int, update: BookmarkUpdate) -> Bookmark | None:
        """Update selected bookmark fields and return the updated row."""

        current = self.get_bookmark(bookmark_id)
        if current is None:
            return None
        title = update.title if update.title is not None else current.title
        tags = normalize_tags(update.tags) if update.tags is not None else current.tags
        desc = update.desc if update.desc is not None else current.desc
        with connect_db(self.path) as connection:
            connection.execute(
                "UPDATE bookmarks SET title = ?, tags = ?, description = ? WHERE id = ?",
                (title, tags_to_db(tags), desc, bookmark_id),
            )
            connection.commit()
            row = connection.execute("SELECT * FROM bookmarks WHERE id = ?", (bookmark_id,)).fetchone()
        return row_to_bookmark(row) if row is not None else None

    def tag_counts(self) -> dict[str, int]:
        """Return tag frequencies across all bookmarks."""

        counts: dict[str, int] = {}
        for bookmark in self.list_bookmarks(limit=None, sort="title"):
            for tag in bookmark.tags:
                counts[tag] = counts.get(tag, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: item[0].lower()))

    def stats(self) -> dict[str, int]:
        """Return summary statistics."""

        with connect_db(self.path) as connection:
            total = connection.execute("SELECT COUNT(*) AS count FROM bookmarks").fetchone()["count"]
        tags = self.tag_counts()
        return {
            "total_bookmarks": int(total),
            "unique_tags": len(tags),
        }
