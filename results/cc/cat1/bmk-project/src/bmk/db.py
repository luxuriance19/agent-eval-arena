"""SQLite database operations for bookmark storage."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from bmk.models import Bookmark

DEFAULT_DB_PATH = Path.home() / ".bmk" / "bookmarks.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS bookmarks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url         TEXT    NOT NULL UNIQUE,
    title       TEXT    NOT NULL DEFAULT '',
    tags        TEXT    NOT NULL DEFAULT '',
    description TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL
)
"""


def _ensure_db(db_path: Path) -> None:
    """Create the database directory and table if they don't exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open (and initialise) a database connection."""
    _ensure_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute(_CREATE_TABLE)
    conn.commit()
    return conn


def add_bookmark(conn: sqlite3.Connection, bm: Bookmark) -> int:
    """Insert a bookmark and return its new id.

    Raises sqlite3.IntegrityError if the URL already exists.
    """
    cur = conn.execute(
        "INSERT INTO bookmarks (url, title, tags, description, created_at) VALUES (?, ?, ?, ?, ?)",
        (bm.url, bm.title, bm.tags_csv, bm.description, bm.created_at),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def get_bookmark(conn: sqlite3.Connection, *, id: int) -> Bookmark | None:
    """Fetch a single bookmark by id."""
    row = conn.execute("SELECT id, url, title, tags, description, created_at FROM bookmarks WHERE id = ?", (id,)).fetchone()
    return Bookmark.from_row(row) if row else None


def list_bookmarks(
    conn: sqlite3.Connection,
    *,
    tag: str | None = None,
    limit: int | None = None,
    sort: str = "date",
) -> list[Bookmark]:
    """List bookmarks with optional tag filter, limit, and sort order."""
    order = "created_at DESC" if sort == "date" else "title ASC"
    query = "SELECT id, url, title, tags, description, created_at FROM bookmarks"
    params: list[str] = []

    if tag:
        query += " WHERE (',' || tags || ',') LIKE ?"
        params.append(f"%,{tag},%")

    query += f" ORDER BY {order}"

    if limit is not None:
        query += " LIMIT ?"
        params.append(str(limit))

    rows = conn.execute(query, params).fetchall()
    return [Bookmark.from_row(r) for r in rows]


def delete_bookmark(conn: sqlite3.Connection, *, id: int) -> bool:
    """Delete a bookmark by id. Returns True if a row was deleted."""
    cur = conn.execute("DELETE FROM bookmarks WHERE id = ?", (id,))
    conn.commit()
    return cur.rowcount > 0


def edit_bookmark(
    conn: sqlite3.Connection,
    *,
    id: int,
    title: str | None = None,
    tags: list[str] | None = None,
    description: str | None = None,
) -> bool:
    """Update bookmark fields. Only non-None values are changed. Returns True if a row was updated."""
    updates: list[str] = []
    params: list[str] = []

    if title is not None:
        updates.append("title = ?")
        params.append(title)
    if tags is not None:
        updates.append("tags = ?")
        params.append(",".join(tags))
    if description is not None:
        updates.append("description = ?")
        params.append(description)

    if not updates:
        return False

    params.append(str(id))
    query = f"UPDATE bookmarks SET {', '.join(updates)} WHERE id = ?"
    cur = conn.execute(query, params)
    conn.commit()
    return cur.rowcount > 0


def all_tags_with_counts(conn: sqlite3.Connection) -> list[tuple[str, int]]:
    """Return all tags with their bookmark counts, sorted by count descending."""
    rows = conn.execute("SELECT tags FROM bookmarks WHERE tags != ''").fetchall()
    counts: dict[str, int] = {}
    for (tags_csv,) in rows:
        for tag in tags_csv.split(","):
            tag = tag.strip()
            if tag:
                counts[tag] = counts.get(tag, 0) + 1
    return sorted(counts.items(), key=lambda x: x[1], reverse=True)


def get_stats(conn: sqlite3.Connection) -> dict[str, int]:
    """Return basic statistics about the bookmark database."""
    total = conn.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0]
    tag_counts = all_tags_with_counts(conn)
    unique_tags = len(tag_counts)
    return {"total_bookmarks": total, "unique_tags": unique_tags}


def get_all_bookmarks(conn: sqlite3.Connection) -> list[Bookmark]:
    """Fetch all bookmarks (used for search and export)."""
    rows = conn.execute("SELECT id, url, title, tags, description, created_at FROM bookmarks ORDER BY created_at DESC").fetchall()
    return [Bookmark.from_row(r) for r in rows]
