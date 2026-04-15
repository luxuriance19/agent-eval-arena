from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

import pytest

from bmk import cli
from bmk.db import BookmarkDB, duplicate_url_exists, init_db
from bmk.models import BookmarkCreate, BookmarkUpdate
from bmk.search import fuzzy_match_score


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / ".bmk" / "bookmarks.db"


@pytest.fixture()
def db(db_path: Path) -> BookmarkDB:
    init_db(db_path)
    return BookmarkDB(db_path)


def test_init_db_creates_parent_directory_and_database(db_path: Path) -> None:
    init_db(db_path)

    assert db_path.parent.exists()
    assert db_path.exists()


def test_add_bookmark_stores_tags_and_fetches_title_when_missing(db: BookmarkDB, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "fetch_page_title", lambda url: "Fetched Title")

    bookmark = cli.add_bookmark(
        db,
        "https://example.com",
        title=None,
        tags="python,tools",
        desc="Useful site",
    )

    assert bookmark.title == "Fetched Title"
    assert bookmark.tags == ["python", "tools"]
    stored = db.get_bookmark(bookmark.id)
    assert stored is not None
    assert stored.tags == ["python", "tools"]


def test_add_bookmark_rejects_invalid_url(db: BookmarkDB) -> None:
    with pytest.raises(ValueError, match="Invalid URL"):
        cli.add_bookmark(db, "notaurl", title="Bad", tags=None, desc=None)


def test_add_bookmark_rejects_duplicate_url(db: BookmarkDB, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "fetch_page_title", lambda url: "Fetched Title")
    cli.add_bookmark(db, "https://example.com", title=None, tags=None, desc=None)

    with pytest.raises(ValueError, match="already exists"):
        cli.add_bookmark(db, "https://example.com", title="Other", tags=None, desc=None)

    assert duplicate_url_exists(db_path=db.path, url="https://example.com") is True


def test_list_bookmarks_can_filter_by_tag_and_sort_by_title(db: BookmarkDB) -> None:
    db.add_bookmark(BookmarkCreate(url="https://b.com", title="Beta", tags=["work"], desc=None))
    db.add_bookmark(BookmarkCreate(url="https://a.com", title="Alpha", tags=["work", "ref"], desc=None))
    db.add_bookmark(BookmarkCreate(url="https://c.com", title="Gamma", tags=["personal"], desc=None))

    bookmarks = db.list_bookmarks(tag="work", limit=10, sort="title")

    assert [bookmark.title for bookmark in bookmarks] == ["Alpha", "Beta"]


def test_search_bookmarks_uses_fuzzy_matching(db: BookmarkDB) -> None:
    db.add_bookmark(BookmarkCreate(url="https://docs.python.org", title="Python Documentation", tags=["python"], desc="Official docs"))
    db.add_bookmark(BookmarkCreate(url="https://sqlite.org", title="SQLite Home", tags=["db"], desc="Database"))

    results = cli.search_bookmarks(db, "pythn docs")

    assert results
    assert results[0].title == "Python Documentation"
    assert fuzzy_match_score("pythn docs", "Python Documentation") > fuzzy_match_score("pythn docs", "SQLite Home")


def test_edit_bookmark_updates_selected_fields(db: BookmarkDB) -> None:
    bookmark = db.add_bookmark(BookmarkCreate(url="https://example.com", title="Old", tags=["one"], desc="before"))

    updated = db.edit_bookmark(bookmark.id, BookmarkUpdate(title="New", tags=["two", "three"], desc="after"))

    assert updated is not None
    assert updated.title == "New"
    assert updated.tags == ["two", "three"]
    assert updated.desc == "after"


def test_delete_bookmark_removes_row(db: BookmarkDB) -> None:
    bookmark = db.add_bookmark(BookmarkCreate(url="https://example.com", title="Title", tags=[], desc=None))

    deleted = db.delete_bookmark(bookmark.id)

    assert deleted is True
    assert db.get_bookmark(bookmark.id) is None


def test_tags_returns_counts(db: BookmarkDB) -> None:
    db.add_bookmark(BookmarkCreate(url="https://a.com", title="A", tags=["python", "ref"], desc=None))
    db.add_bookmark(BookmarkCreate(url="https://b.com", title="B", tags=["python"], desc=None))

    assert db.tag_counts() == {"python": 2, "ref": 1}


def test_export_json_and_import_json_round_trip(db: BookmarkDB, tmp_path: Path) -> None:
    bookmark = db.add_bookmark(BookmarkCreate(url="https://example.com", title="Title", tags=["python"], desc="desc"))
    export_path = tmp_path / "export.json"

    cli.export_bookmarks(db, export_path, "json")

    imported_db_path = tmp_path / "other" / "bookmarks.db"
    init_db(imported_db_path)
    imported_db = BookmarkDB(imported_db_path)
    cli.import_bookmarks(imported_db, export_path, "json")

    bookmarks = imported_db.list_bookmarks()
    assert len(bookmarks) == 1
    assert bookmarks[0].url == bookmark.url
    assert bookmarks[0].tags == ["python"]


def test_export_csv_writes_expected_headers(db: BookmarkDB, tmp_path: Path) -> None:
    db.add_bookmark(BookmarkCreate(url="https://example.com", title="Title", tags=["python", "ref"], desc="desc"))
    export_path = tmp_path / "export.csv"

    cli.export_bookmarks(db, export_path, "csv")

    with export_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0]["url"] == "https://example.com"
    assert rows[0]["tags"] == "python,ref"


def test_stats_returns_expected_counts(db: BookmarkDB) -> None:
    db.add_bookmark(BookmarkCreate(url="https://a.com", title="A", tags=["python", "ref"], desc=None))
    db.add_bookmark(BookmarkCreate(url="https://b.com", title="B", tags=["python"], desc=None))

    stats = db.stats()

    assert stats["total_bookmarks"] == 2
    assert stats["unique_tags"] == 2


def test_fetch_page_title_failure_falls_back_to_url(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(url: str, timeout: int = 5):
        raise OSError("network down")

    monkeypatch.setattr(cli.request, "urlopen", fake_urlopen)

    assert cli.fetch_page_title("https://example.com") == "https://example.com"


def test_html_export_contains_bookmark_titles(db: BookmarkDB, tmp_path: Path) -> None:
    db.add_bookmark(BookmarkCreate(url="https://example.com", title="Example", tags=["python"], desc="desc"))
    export_path = tmp_path / "export.html"

    cli.export_bookmarks(db, export_path, "html")

    html = export_path.read_text(encoding="utf-8")
    assert "<html" in html.lower()
    assert "Example" in html
