"""Import/export functionality."""
import json
import csv
from typing import List
from pathlib import Path
from .models import Bookmark


def export_json(bookmarks: List[Bookmark], output_path: Path) -> None:
    """Export bookmarks to JSON format."""
    data = []
    for bm in bookmarks:
        data.append({
            "id": bm.id,
            "url": bm.url,
            "title": bm.title,
            "tags": bm.tags,
            "description": bm.description,
            "created_at": bm.created_at.isoformat()
        })
    
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)


def export_csv(bookmarks: List[Bookmark], output_path: Path) -> None:
    """Export bookmarks to CSV format."""
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "url", "title", "tags", "description", "created_at"])
        
        for bm in bookmarks:
            writer.writerow([
                bm.id,
                bm.url,
                bm.title,
                bm.tags_str(),
                bm.description,
                bm.created_at.isoformat()
            ])


def export_html(bookmarks: List[Bookmark], output_path: Path) -> None:
    """Export bookmarks to HTML format."""
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Bookmarks</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .bookmark { margin-bottom: 20px; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
        .bookmark h3 { margin: 0 0 5px 0; }
        .bookmark a { color: #0066cc; text-decoration: none; }
        .bookmark a:hover { text-decoration: underline; }
        .tags { color: #666; font-size: 0.9em; }
        .description { color: #333; margin-top: 5px; }
        .date { color: #999; font-size: 0.8em; }
    </style>
</head>
<body>
    <h1>Bookmarks</h1>
"""
    
    for bm in bookmarks:
        html += f"""
    <div class="bookmark">
        <h3><a href="{bm.url}">{bm.title}</a></h3>
        <div class="tags">Tags: {", ".join(bm.tags) if bm.tags else "None"}</div>
        <div class="description">{bm.description}</div>
        <div class="date">Added: {bm.created_at.strftime("%Y-%m-%d %H:%M:%S")}</div>
    </div>
"""
    
    html += """
</body>
</html>
"""
    
    with open(output_path, "w") as f:
        f.write(html)


def import_json(file_path: Path) -> List[dict]:
    """Import bookmarks from JSON format."""
    with open(file_path, "r") as f:
        data = json.load(f)
    
    bookmarks = []
    for item in data:
        bookmarks.append({
            "url": item["url"],
            "title": item["title"],
            "tags": item.get("tags", []),
            "description": item.get("description", "")
        })
    return bookmarks


def import_csv(file_path: Path) -> List[dict]:
    """Import bookmarks from CSV format."""
    bookmarks = []
    
    with open(file_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tags = Bookmark.parse_tags(row.get("tags", ""))
            bookmarks.append({
                "url": row["url"],
                "title": row["title"],
                "tags": tags,
                "description": row.get("description", "")
            })
    
    return bookmarks
