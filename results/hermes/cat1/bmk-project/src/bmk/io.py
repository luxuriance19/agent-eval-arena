from __future__ import annotations

import csv
import html
import json
from pathlib import Path

from bmk.models import Bookmark


EXPORT_FIELDS: list[str] = ["id", "url", "title", "tags", "desc", "created_at"]


def bookmarks_to_dicts(bookmarks: list[Bookmark]) -> list[dict[str, object]]:
    """Convert bookmarks into serializable dictionaries."""

    return [
        {
            "id": bookmark.id,
            "url": bookmark.url,
            "title": bookmark.title,
            "tags": ",".join(bookmark.tags),
            "desc": bookmark.desc,
            "created_at": bookmark.created_at,
        }
        for bookmark in bookmarks
    ]


def export_json(bookmarks: list[Bookmark], output: Path) -> None:
    """Write bookmarks as JSON."""

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bookmarks_to_dicts(bookmarks), indent=2), encoding="utf-8")


def export_csv(bookmarks: list[Bookmark], output: Path) -> None:
    """Write bookmarks as CSV."""

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        writer.writerows(bookmarks_to_dicts(bookmarks))


def export_html(bookmarks: list[Bookmark], output: Path) -> None:
    """Write bookmarks as a simple HTML document."""

    output.parent.mkdir(parents=True, exist_ok=True)
    items = []
    for bookmark in bookmarks:
        tags = ", ".join(html.escape(tag) for tag in bookmark.tags) or "-"
        desc = html.escape(bookmark.desc or "")
        items.append(
            "<li>"
            f'<a href="{html.escape(bookmark.url)}">{html.escape(bookmark.title)}</a>'
            f"<div>Tags: {tags}</div>"
            f"<div>Description: {desc}</div>"
            "</li>"
        )
    document = "\n".join(
        [
            "<!DOCTYPE html>",
            "<html>",
            "<head><meta charset=\"utf-8\"><title>bmk export</title></head>",
            "<body>",
            "<h1>Bookmarks</h1>",
            "<ul>",
            *items,
            "</ul>",
            "</body>",
            "</html>",
        ]
    )
    output.write_text(document, encoding="utf-8")


def load_json(input_file: Path) -> list[dict[str, object]]:
    """Load bookmark records from a JSON file."""

    data = json.loads(input_file.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("JSON import must contain a list of bookmarks")
    return [dict(item) for item in data]


def load_csv(input_file: Path) -> list[dict[str, object]]:
    """Load bookmark records from a CSV file."""

    with input_file.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]
