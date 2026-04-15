"""Test suite for bmk bookmark manager."""
import pytest
from pathlib import Path
from datetime import datetime
from bmk.db import BookmarkDB
from bmk.models import Bookmark
from bmk.search import fuzzy_search
from bmk.io import export_json, export_csv, export_html, import_json, import_csv
from bmk.cli import validate_url, fetch_page_title
from unittest.mock import patch


@pytest.fixture
def db(tmp_path: Path) -> BookmarkDB:
    """Create a temporary database for testing."""
    db_path = tmp_path / "test.db"
    return BookmarkDB(db_path)


@pytest.fixture
def sample_bookmarks(db: BookmarkDB) -> list:
    """Create sample bookmarks for testing."""
    db.add_bookmark("https://example.com", "Example Site", ["test", "demo"], "A test site")
    db.add_bookmark("https://python.org", "Python", ["programming", "python"], "Python homepage")
    db.add_bookmark("https://github.com", "GitHub", ["code", "git"], "Code hosting")
    return db.get_all_bookmarks()


def test_add_bookmark(db: BookmarkDB) -> None:
    """Test adding a bookmark."""
    bookmark_id = db.add_bookmark("https://test.com", "Test", ["tag1"], "Description")
    assert bookmark_id > 0
    
    bookmarks = db.get_all_bookmarks()
    assert len(bookmarks) == 1
    assert bookmarks[0].url == "https://test.com"
    assert bookmarks[0].title == "Test"
    assert bookmarks[0].tags == ["tag1"]


def test_duplicate_url(db: BookmarkDB) -> None:
    """Test that duplicate URLs are prevented."""
    db.add_bookmark("https://test.com", "Test", [], "")
    
    with pytest.raises(Exception):
        db.add_bookmark("https://test.com", "Test2", [], "")


def test_list_bookmarks(db: BookmarkDB, sample_bookmarks: list) -> None:
    """Test listing bookmarks."""
    bookmarks = db.get_all_bookmarks()
    assert len(bookmarks) == 3


def test_list_with_tag_filter(db: BookmarkDB, sample_bookmarks: list) -> None:
    """Test filtering bookmarks by tag."""
    bookmarks = db.get_all_bookmarks(tag="python")
    assert len(bookmarks) == 1
    assert bookmarks[0].url == "https://python.org"


def test_list_with_limit(db: BookmarkDB, sample_bookmarks: list) -> None:
    """Test limiting bookmark results."""
    bookmarks = db.get_all_bookmarks(limit=2)
    assert len(bookmarks) == 2


def test_search_bookmarks(db: BookmarkDB, sample_bookmarks: list) -> None:
    """Test searching bookmarks."""
    results = db.search_bookmarks("python")
    assert len(results) >= 1
    assert any("python" in bm.url.lower() or "python" in bm.title.lower() for bm in results)


def test_fuzzy_search(db: BookmarkDB, sample_bookmarks: list) -> None:
    """Test fuzzy search functionality."""
    all_bookmarks = db.get_all_bookmarks()
    results = fuzzy_search(all_bookmarks, "pyton")  # Typo
    assert len(results) > 0


def test_delete_bookmark(db: BookmarkDB) -> None:
    """Test deleting a bookmark."""
    bookmark_id = db.add_bookmark("https://test.com", "Test", [], "")
    assert db.delete_bookmark(bookmark_id) is True
    assert db.delete_bookmark(bookmark_id) is False  # Already deleted


def test_edit_bookmark(db: BookmarkDB) -> None:
    """Test editing a bookmark."""
    bookmark_id = db.add_bookmark("https://test.com", "Test", ["old"], "Old desc")
    
    success = db.update_bookmark(bookmark_id, title="New Title", tags=["new"], description="New desc")
    assert success is True
    
    bookmarks = db.get_all_bookmarks()
    assert bookmarks[0].title == "New Title"
    assert bookmarks[0].tags == ["new"]
    assert bookmarks[0].description == "New desc"


def test_tags_list(db: BookmarkDB, sample_bookmarks: list) -> None:
    """Test listing all tags with counts."""
    tags = db.get_all_tags()
    assert "test" in tags
    assert "python" in tags
    assert tags["test"] == 1
    assert tags["python"] == 1


def test_stats(db: BookmarkDB, sample_bookmarks: list) -> None:
    """Test statistics."""
    stats = db.get_stats()
    assert stats["total_bookmarks"] == 3
    assert stats["unique_tags"] > 0


def test_export_json(db: BookmarkDB, sample_bookmarks: list, tmp_path: Path) -> None:
    """Test JSON export."""
    output_file = tmp_path / "export.json"
    bookmarks = db.get_all_bookmarks()
    export_json(bookmarks, output_file)
    
    assert output_file.exists()
    imported = import_json(output_file)
    assert len(imported) == 3


def test_export_csv(db: BookmarkDB, sample_bookmarks: list, tmp_path: Path) -> None:
    """Test CSV export."""
    output_file = tmp_path / "export.csv"
    bookmarks = db.get_all_bookmarks()
    export_csv(bookmarks, output_file)
    
    assert output_file.exists()
    imported = import_csv(output_file)
    assert len(imported) == 3


def test_export_html(db: BookmarkDB, sample_bookmarks: list, tmp_path: Path) -> None:
    """Test HTML export."""
    output_file = tmp_path / "export.html"
    bookmarks = db.get_all_bookmarks()
    export_html(bookmarks, output_file)
    
    assert output_file.exists()
    content = output_file.read_text()
    assert "<html>" in content
    assert "Example Site" in content


def test_import_json(db: BookmarkDB, tmp_path: Path) -> None:
    """Test JSON import."""
    json_file = tmp_path / "import.json"
    json_file.write_text('[{"url": "https://new.com", "title": "New", "tags": ["test"], "description": "Desc"}]')
    
    imported = import_json(json_file)
    assert len(imported) == 1
    assert imported[0]["url"] == "https://new.com"


def test_import_csv(db: BookmarkDB, tmp_path: Path) -> None:
    """Test CSV import."""
    csv_file = tmp_path / "import.csv"
    csv_file.write_text('url,title,tags,description\nhttps://new.com,New,test,Desc\n')
    
    imported = import_csv(csv_file)
    assert len(imported) == 1
    assert imported[0]["url"] == "https://new.com"


def test_url_validation() -> None:
    """Test URL validation."""
    assert validate_url("https://example.com") is True
    assert validate_url("http://example.com") is True
    assert validate_url("not-a-url") is False
    assert validate_url("") is False


def test_fetch_page_title_mock() -> None:
    """Test page title fetching with mock."""
    with patch('bmk.cli.fetch_page_title') as mock_fetch:
        mock_fetch.return_value = "Mocked Title"
        title = mock_fetch("https://example.com")
        assert title == "Mocked Title"


def test_parse_tags() -> None:
    """Test tag parsing."""
    tags = Bookmark.parse_tags("tag1, tag2, tag3")
    assert tags == ["tag1", "tag2", "tag3"]
    
    tags = Bookmark.parse_tags("")
    assert tags == []


def test_tags_str() -> None:
    """Test tags to string conversion."""
    bookmark = Bookmark(
        id=1,
        url="https://test.com",
        title="Test",
        tags=["tag1", "tag2"],
        description="",
        created_at=datetime.now()
    )
    assert bookmark.tags_str() == "tag1,tag2"
