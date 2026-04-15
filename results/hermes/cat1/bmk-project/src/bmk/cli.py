from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence
from urllib import request
from urllib.error import URLError
from urllib.parse import urlparse

from bmk.db import BookmarkDB, duplicate_url_exists
from bmk.io import export_csv, export_html, export_json, load_csv, load_json
from bmk.models import Bookmark, BookmarkCreate, BookmarkUpdate, normalize_tags
from bmk.search import search_bookmarks as fuzzy_search_bookmarks


DEFAULT_DB_PATH = Path.home() / ".bmk" / "bookmarks.db"


def get_db_path() -> Path:
    """Return the default SQLite database path."""

    return DEFAULT_DB_PATH


def parse_tags(raw_tags: str | None) -> list[str]:
    """Parse comma-separated tags into a list."""

    if raw_tags is None:
        return []
    return normalize_tags(raw_tags.split(","))


def validate_url(url: str) -> str:
    """Validate a URL and return it unchanged when valid."""

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")
    return url


def fetch_page_title(url: str) -> str:
    """Fetch the page title for a URL, falling back to the URL on failure."""

    try:
        with request.urlopen(url, timeout=5) as response:
            content = response.read(4096).decode("utf-8", errors="ignore")
    except (OSError, URLError):
        return url
    start_marker = "<title>"
    end_marker = "</title>"
    lowered = content.lower()
    start = lowered.find(start_marker)
    end = lowered.find(end_marker)
    if start == -1 or end == -1 or end <= start:
        return url
    title = content[start + len(start_marker) : end].strip()
    return title or url


def add_bookmark(db: BookmarkDB, url: str, title: str | None, tags: str | None, desc: str | None) -> Bookmark:
    """Validate and add a bookmark."""

    valid_url = validate_url(url)
    if duplicate_url_exists(db.path, valid_url):
        raise ValueError(f"Bookmark for URL already exists: {valid_url}")
    final_title = title or fetch_page_title(valid_url)
    return db.add_bookmark(BookmarkCreate(url=valid_url, title=final_title, tags=parse_tags(tags), desc=desc))


def search_bookmarks(db: BookmarkDB, query: str) -> list[Bookmark]:
    """Search bookmarks using fuzzy matching."""

    return fuzzy_search_bookmarks(query, db.list_bookmarks(limit=None, sort="title"))


def export_bookmarks(db: BookmarkDB, output: Path, fmt: str) -> None:
    """Export bookmarks in the selected format."""

    bookmarks = db.list_bookmarks(limit=None, sort="title")
    if fmt == "json":
        export_json(bookmarks, output)
    elif fmt == "csv":
        export_csv(bookmarks, output)
    elif fmt == "html":
        export_html(bookmarks, output)
    else:
        raise ValueError(f"Unsupported export format: {fmt}")


def import_bookmarks(db: BookmarkDB, input_file: Path, fmt: str) -> int:
    """Import bookmarks from JSON or CSV, skipping duplicates."""

    records = load_json(input_file) if fmt == "json" else load_csv(input_file)
    imported = 0
    for record in records:
        url = validate_url(str(record["url"]))
        if duplicate_url_exists(db.path, url):
            continue
        db.add_bookmark(
            BookmarkCreate(
                url=url,
                title=str(record.get("title") or url),
                tags=parse_tags(str(record.get("tags") or "")),
                desc=(str(record["desc"]) if record.get("desc") not in {None, ""} else None),
            )
        )
        imported += 1
    return imported


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""

    parser = argparse.ArgumentParser(prog="bmk", description="SQLite bookmark manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add a bookmark")
    add_parser.add_argument("url")
    add_parser.add_argument("--title")
    add_parser.add_argument("--tags")
    add_parser.add_argument("--desc")

    list_parser = subparsers.add_parser("list", help="List bookmarks")
    list_parser.add_argument("--tag")
    list_parser.add_argument("--limit", type=int)
    list_parser.add_argument("--sort", choices=["date", "title"], default="date")

    search_parser = subparsers.add_parser("search", help="Search bookmarks")
    search_parser.add_argument("query")

    delete_parser = subparsers.add_parser("delete", help="Delete a bookmark")
    delete_parser.add_argument("id", type=int)

    edit_parser = subparsers.add_parser("edit", help="Edit a bookmark")
    edit_parser.add_argument("id", type=int)
    edit_parser.add_argument("--title")
    edit_parser.add_argument("--tags")
    edit_parser.add_argument("--desc")

    subparsers.add_parser("tags", help="List tags")

    export_parser = subparsers.add_parser("export", help="Export bookmarks")
    export_parser.add_argument("--format", choices=["json", "csv", "html"], default="json")
    export_parser.add_argument("--output")

    import_parser = subparsers.add_parser("import", help="Import bookmarks")
    import_parser.add_argument("file")
    import_parser.add_argument("--format", choices=["json", "csv"], default="json")

    subparsers.add_parser("stats", help="Show bookmark statistics")
    return parser


def format_bookmark(bookmark: Bookmark) -> str:
    """Return a human-readable bookmark line."""

    tag_text = ", ".join(bookmark.tags) if bookmark.tags else "-"
    desc = bookmark.desc or ""
    return f"[{bookmark.id}] {bookmark.title} | {bookmark.url} | tags={tag_text} | desc={desc}"


def handle_command(args: argparse.Namespace, db: BookmarkDB) -> str:
    """Execute a parsed CLI command and return printable output."""

    if args.command == "add":
        bookmark = add_bookmark(db, args.url, args.title, args.tags, args.desc)
        return f"Added bookmark {bookmark.id}: {bookmark.title}"
    if args.command == "list":
        bookmarks = db.list_bookmarks(tag=args.tag, limit=args.limit, sort=args.sort)
        return "\n".join(format_bookmark(bookmark) for bookmark in bookmarks) or "No bookmarks found."
    if args.command == "search":
        bookmarks = search_bookmarks(db, args.query)
        return "\n".join(format_bookmark(bookmark) for bookmark in bookmarks) or "No matching bookmarks found."
    if args.command == "delete":
        deleted = db.delete_bookmark(args.id)
        return f"Deleted bookmark {args.id}." if deleted else f"Bookmark {args.id} not found."
    if args.command == "edit":
        updated = db.edit_bookmark(args.id, BookmarkUpdate(title=args.title, tags=parse_tags(args.tags) if args.tags is not None else None, desc=args.desc))
        return format_bookmark(updated) if updated is not None else f"Bookmark {args.id} not found."
    if args.command == "tags":
        counts = db.tag_counts()
        return "\n".join(f"{tag}: {count}" for tag, count in counts.items()) or "No tags found."
    if args.command == "export":
        output = Path(args.output) if args.output else Path(f"bookmarks.{args.format}")
        export_bookmarks(db, output, args.format)
        return f"Exported bookmarks to {output}"
    if args.command == "import":
        imported = import_bookmarks(db, Path(args.file), args.format)
        return f"Imported {imported} bookmarks."
    if args.command == "stats":
        stats = db.stats()
        return "\n".join(f"{key}: {value}" for key, value in stats.items())
    raise ValueError(f"Unsupported command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the bmk command-line interface."""

    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    db = BookmarkDB(get_db_path())
    try:
        output = handle_command(args, db)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
