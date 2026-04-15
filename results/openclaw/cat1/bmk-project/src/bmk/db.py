"""Database operations for bookmarks."""
import sqlite3
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from datetime import datetime
from .models import Bookmark


class BookmarkDB:
    """Handles SQLite database operations for bookmarks."""
    
    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Initialize database connection."""
        if db_path is None:
            db_path = Path.home() / ".bmk" / "bookmarks.db"
        
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    tags TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    
    def add_bookmark(self, url: str, title: str, tags: List[str], description: str) -> int:
        """Add a new bookmark. Returns the bookmark ID."""
        tags_str = ",".join(tags) if tags else ""
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO bookmarks (url, title, tags, description) VALUES (?, ?, ?, ?)",
                (url, title, tags_str, description)
            )
            conn.commit()
            return cursor.lastrowid
    
    def get_all_bookmarks(self, tag: Optional[str] = None, limit: Optional[int] = None, 
                         sort_by: str = "date") -> List[Bookmark]:
        """Retrieve all bookmarks, optionally filtered by tag."""
        query = "SELECT id, url, title, tags, description, created_at FROM bookmarks"
        params: Tuple = ()
        
        if tag:
            query += " WHERE tags LIKE ?"
            params = (f"%{tag}%",)
        
        if sort_by == "title":
            query += " ORDER BY title"
        else:
            query += " ORDER BY created_at DESC"
        
        if limit:
            query += " LIMIT ?"
            params = params + (limit,)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
        
        bookmarks = []
        for row in rows:
            bookmarks.append(Bookmark(
                id=row["id"],
                url=row["url"],
                title=row["title"],
                tags=Bookmark.parse_tags(row["tags"]),
                description=row["description"] or "",
                created_at=datetime.fromisoformat(row["created_at"])
            ))
        return bookmarks
    
    def search_bookmarks(self, query: str) -> List[Bookmark]:
        """Search bookmarks by URL, title, tags, or description."""
        sql = """
            SELECT id, url, title, tags, description, created_at 
            FROM bookmarks 
            WHERE url LIKE ? OR title LIKE ? OR tags LIKE ? OR description LIKE ?
        """
        pattern = f"%{query}%"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, (pattern, pattern, pattern, pattern))
            rows = cursor.fetchall()
        
        bookmarks = []
        for row in rows:
            bookmarks.append(Bookmark(
                id=row["id"],
                url=row["url"],
                title=row["title"],
                tags=Bookmark.parse_tags(row["tags"]),
                description=row["description"] or "",
                created_at=datetime.fromisoformat(row["created_at"])
            ))
        return bookmarks
    
    def delete_bookmark(self, bookmark_id: int) -> bool:
        """Delete a bookmark by ID. Returns True if deleted."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def update_bookmark(self, bookmark_id: int, title: Optional[str] = None, 
                       tags: Optional[List[str]] = None, description: Optional[str] = None) -> bool:
        """Update bookmark fields. Returns True if updated."""
        updates = []
        params = []
        
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
        
        params.append(bookmark_id)
        sql = f"UPDATE bookmarks SET {', '.join(updates)} WHERE id = ?"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor.rowcount > 0
    
    def get_all_tags(self) -> Dict[str, int]:
        """Get all tags with their usage counts."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT tags FROM bookmarks WHERE tags IS NOT NULL AND tags != ''")
            rows = cursor.fetchall()
        
        tag_counts: Dict[str, int] = {}
        for row in rows:
            tags = Bookmark.parse_tags(row[0])
            for tag in tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        return tag_counts
    
    def get_stats(self) -> Dict[str, int]:
        """Get bookmark statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM bookmarks")
            total = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(DISTINCT tags) FROM bookmarks WHERE tags IS NOT NULL AND tags != ''")
            unique_tags = len(self.get_all_tags())
        
        return {
            "total_bookmarks": total,
            "unique_tags": unique_tags
        }
    
    def url_exists(self, url: str) -> bool:
        """Check if a URL already exists in the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT 1 FROM bookmarks WHERE url = ?", (url,))
            return cursor.fetchone() is not None
