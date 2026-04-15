"""Tests for bmk bookmark manager."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from bmk.cli import cmd_add, cmd_delete, cmd_list, cmd_search, cmd_stats, build_parser, fetch_title
from bmk.db import add_bookmark, get_all_bookmarks, get_connection, list_bookmarks, edit_bookmark, delete_bookmark, all_tags_with_counts, get_stats
from bmk.io import export_json, export_csv, export_html, import_json, import_csv, import_bookmarks, export_bookmarks
from bmk.models import Bookmark
from bmk.search import fuzzy_search


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """Return a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture()
def conn(db_path: Path) -> sqlite3.Connection:
    """Return an initialised in-memory-like connection using tmp_path."""
    c = get_connection(db_path)
    yield c  # type: ignore[misc]
    c.close()


def _sample_bookmark(*, url: str = "https://example.com", title: str = "Example", tags: list[str] | None = None) -> Bookmark:
    return Bookmark(url=url, title=title, tags=tags or [])


# ── DB tests ──────────────────────────────────────────────────────────

class TestDatabase:
    def test_add_and_list(self, conn: sqlite3.Connection) -> None:
        """Adding a bookmark then listing returns it."""
        bm = _sample_bookmark(tags=["dev", "test"])
        bm_id = add_bookmark(conn, bm)
        assert bm_id >= 1

        results = list_bookmarks(conn)
        assert len(results) == 1
        assert results[0].url == "https://example.com"
        assert results[0].tags == ["dev", "test"]

    def test_duplicate_url_raises(self, conn: sqlite3.Connection) -> None:
        """Adding the same URL twice raises IntegrityError."""
        add_bookmark(conn, _sample_bookmark())
        with pytest.raises(sqlite3.IntegrityError):
            add_bookmark(conn, _sample_bookmark())

    def test_delete_bookmark(self, conn: sqlite3.Connection) -> None:
        """Deleting a bookmark removes it from the database."""
        bm_id = add_bookmark(conn, _sample_bookmark())
        assert delete_bookmark(conn, id=bm_id) is True
        assert list_bookmarks(conn) == []

    def test_delete_nonexistent(self, conn: sqlite3.Connection) -> None:
        """Deleting a nonexistent bookmark returns False."""
        assert delete_bookmark(conn, id=999) is False

    def test_edit_bookmark(self, conn: sqlite3.Connection) -> None:
        """Editing a bookmark updates only the specified fields."""
        bm_id = add_bookmark(conn, _sample_bookmark(title="Old"))
        assert edit_bookmark(conn, id=bm_id, title="New") is True
        results = list_bookmarks(conn)
        assert results[0].title == "New"

    def test_list_filter_by_tag(self, conn: sqlite3.Connection) -> None:
        """Listing with a tag filter returns only matching bookmarks."""
        add_bookmark(conn, _sample_bookmark(url="https://a.com", tags=["python"]))
        add_bookmark(conn, _sample_bookmark(url="https://b.com", tags=["rust"]))
        results = list_bookmarks(conn, tag="python")
        assert len(results) == 1
        assert results[0].url == "https://a.com"

    def test_tags_with_counts(self, conn: sqlite3.Connection) -> None:
        """Tag counts are computed correctly."""
        add_bookmark(conn, _sample_bookmark(url="https://a.com", tags=["python", "web"]))
        add_bookmark(conn, _sample_bookmark(url="https://b.com", tags=["python"]))
        counts = dict(all_tags_with_counts(conn))
        assert counts["python"] == 2
        assert counts["web"] == 1

    def test_stats(self, conn: sqlite3.Connection) -> None:
        """Stats returns correct totals."""
        add_bookmark(conn, _sample_bookmark(url="https://a.com", tags=["a"]))
        add_bookmark(conn, _sample_bookmark(url="https://b.com", tags=["b"]))
        stats = get_stats(conn)
        assert stats["total_bookmarks"] == 2
        assert stats["unique_tags"] == 2


# ── Search tests ──────────────────────────────────────────────────────

class TestSearch:
    def test_fuzzy_search_by_title(self) -> None:
        """Fuzzy search matches on title."""
        bms = [
            _sample_bookmark(url="https://a.com", title="Python Tutorial"),
            _sample_bookmark(url="https://b.com", title="Rust Guide"),
        ]
        results = fuzzy_search(bms, "python")
        assert len(results) >= 1
        assert results[0].title == "Python Tutorial"

    def test_fuzzy_search_by_tag(self) -> None:
        """Fuzzy search matches on tags."""
        bms = [_sample_bookmark(url="https://a.com", title="Doc", tags=["python"])]
        results = fuzzy_search(bms, "python")
        assert len(results) == 1

    def test_fuzzy_search_no_results(self) -> None:
        """Fuzzy search returns empty list for no matches."""
        bms = [_sample_bookmark(url="https://a.com", title="Rust Guide")]
        results = fuzzy_search(bms, "zzzznotfound")
        assert results == []


# ── IO tests ──────────────────────────────────────────────────────────

class TestIO:
    def test_export_json_roundtrip(self) -> None:
        """Exporting to JSON and importing back preserves data."""
        bms = [_sample_bookmark(tags=["a", "b"])]
        exported = export_json(bms)
        imported = import_json(exported)
        assert len(imported) == 1
        assert imported[0].url == "https://example.com"
        assert imported[0].tags == ["a", "b"]

    def test_export_csv_roundtrip(self) -> None:
        """Exporting to CSV and importing back preserves data."""
        bms = [_sample_bookmark(tags=["x"])]
        exported = export_csv(bms)
        imported = import_csv(exported)
        assert len(imported) == 1
        assert imported[0].url == "https://example.com"
        assert imported[0].tags == ["x"]

    def test_export_html_contains_link(self) -> None:
        """HTML export contains the bookmark URL as a link."""
        bms = [_sample_bookmark()]
        html = export_html(bms)
        assert "https://example.com" in html
        assert "<a href=" in html

    def test_import_file_not_found(self, tmp_path: Path) -> None:
        """Importing a nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            import_bookmarks(str(tmp_path / "nope.json"))

    def test_export_to_file(self, tmp_path: Path) -> None:
        """Exporting to a file creates the file with content."""
        bms = [_sample_bookmark()]
        out = tmp_path / "out.json"
        export_bookmarks(bms, fmt="json", output=str(out))
        assert out.exists()
        data = json.loads(out.read_text())
        assert len(data) == 1


# ── CLI tests (with mocked title fetch) ──────────────────────────────

class TestCLI:
    def test_add_with_mock_title(self, db_path: Path) -> None:
        """Adding a URL auto-fetches the title (mocked)."""
        with patch("bmk.cli.fetch_title", return_value="Mocked Title"):
            parser = build_parser()
            args = parser.parse_args(["--db", str(db_path), "add", "https://example.com"])
            cmd_add(args, db_path)

        conn = get_connection(db_path)
        bms = get_all_bookmarks(conn)
        conn.close()
        assert len(bms) == 1
        assert bms[0].title == "Mocked Title"

    def test_add_with_explicit_title(self, db_path: Path) -> None:
        """Adding with --title skips auto-fetch."""
        with patch("bmk.cli.fetch_title") as mock_fetch:
            parser = build_parser()
            args = parser.parse_args(["--db", str(db_path), "add", "https://example.com", "--title", "My Title"])
            cmd_add(args, db_path)
            mock_fetch.assert_not_called()

        conn = get_connection(db_path)
        bms = get_all_bookmarks(conn)
        conn.close()
        assert bms[0].title == "My Title"


# ── Model tests ───────────────────────────────────────────────────────

class TestModel:
    def test_from_row(self) -> None:
        """Bookmark.from_row correctly parses a database row."""
        row = (1, "https://example.com", "Title", "a,b,c", "desc", "2024-01-01T00:00:00")
        bm = Bookmark.from_row(row)
        assert bm.id == 1
        assert bm.tags == ["a", "b", "c"]
        assert bm.tags_csv == "a,b,c"

    def test_tags_csv_empty(self) -> None:
        """Empty tags produce an empty CSV string."""
        bm = Bookmark(url="https://x.com")
        assert bm.tags_csv == ""
