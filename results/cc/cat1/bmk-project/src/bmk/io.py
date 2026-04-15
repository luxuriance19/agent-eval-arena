"""Import and export bookmarks in various formats."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from bmk.models import Bookmark


def _bookmark_to_dict(bm: Bookmark) -> dict[str, str | list[str] | int | None]:
    """Convert a Bookmark to a serialisable dict."""
    return {
        "id": bm.id,
        "url": bm.url,
        "title": bm.title,
        "tags": bm.tags,
        "description": bm.description,
        "created_at": bm.created_at,
    }


# ── Export ────────────────────────────────────────────────────────────

def export_json(bookmarks: list[Bookmark]) -> str:
    """Export bookmarks as a JSON string."""
    return json.dumps([_bookmark_to_dict(bm) for bm in bookmarks], indent=2, ensure_ascii=False)


def export_csv(bookmarks: list[Bookmark]) -> str:
    """Export bookmarks as a CSV string."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "url", "title", "tags", "description", "created_at"])
    for bm in bookmarks:
        writer.writerow([bm.id, bm.url, bm.title, bm.tags_csv, bm.description, bm.created_at])
    return buf.getvalue()


def export_html(bookmarks: list[Bookmark]) -> str:
    """Export bookmarks as an HTML document."""
    lines = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'><title>Bookmarks</title></head>",
        "<body><h1>Bookmarks</h1><ul>",
    ]
    for bm in bookmarks:
        tags_str = f" [{bm.tags_csv}]" if bm.tags else ""
        desc_str = f" - {bm.description}" if bm.description else ""
        lines.append(f"  <li><a href='{bm.url}'>{bm.title or bm.url}</a>{tags_str}{desc_str}</li>")
    lines.append("</ul></body></html>")
    return "\n".join(lines)


def export_bookmarks(bookmarks: list[Bookmark], *, fmt: str = "json", output: str | None = None) -> str:
    """Export bookmarks to the given format, optionally writing to a file.

    Returns the exported content as a string.
    """
    exporters = {"json": export_json, "csv": export_csv, "html": export_html}
    if fmt not in exporters:
        raise ValueError(f"Unsupported export format: {fmt!r}. Choose from: {', '.join(exporters)}")

    content = exporters[fmt](bookmarks)

    if output:
        Path(output).write_text(content, encoding="utf-8")

    return content


# ── Import ────────────────────────────────────────────────────────────

def import_json(text: str) -> list[Bookmark]:
    """Parse bookmarks from a JSON string."""
    data = json.loads(text)
    results: list[Bookmark] = []
    for item in data:
        tags = item.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        results.append(
            Bookmark(
                url=item["url"],
                title=item.get("title", ""),
                tags=tags,
                description=item.get("description", ""),
                created_at=item.get("created_at", ""),
            )
        )
    return results


def import_csv(text: str) -> list[Bookmark]:
    """Parse bookmarks from a CSV string."""
    reader = csv.DictReader(io.StringIO(text))
    results: list[Bookmark] = []
    for row in reader:
        tags_raw = row.get("tags", "")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        results.append(
            Bookmark(
                url=row["url"],
                title=row.get("title", ""),
                tags=tags,
                description=row.get("description", ""),
                created_at=row.get("created_at", ""),
            )
        )
    return results


def import_bookmarks(file_path: str, *, fmt: str | None = None) -> list[Bookmark]:
    """Import bookmarks from a file. Format is auto-detected from extension if not given."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Import file not found: {file_path}")

    if fmt is None:
        suffix = path.suffix.lower()
        fmt = {"json": "json", ".json": "json", ".csv": "csv"}.get(suffix)
        if fmt is None:
            raise ValueError(f"Cannot detect format from extension {suffix!r}. Use --format.")

    text = path.read_text(encoding="utf-8")
    importers = {"json": import_json, "csv": import_csv}
    if fmt not in importers:
        raise ValueError(f"Unsupported import format: {fmt!r}. Choose from: {', '.join(importers)}")

    return importers[fmt](text)
