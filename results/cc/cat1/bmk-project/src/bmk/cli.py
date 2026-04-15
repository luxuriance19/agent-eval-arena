"""CLI entry point for bmk bookmark manager."""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from bmk.db import (
    DEFAULT_DB_PATH,
    add_bookmark,
    all_tags_with_counts,
    delete_bookmark,
    edit_bookmark,
    get_all_bookmarks,
    get_connection,
    get_stats,
    list_bookmarks,
)
from bmk.io import export_bookmarks, import_bookmarks
from bmk.models import Bookmark
from bmk.search import fuzzy_search

_URL_RE = re.compile(r"^https?://\S+$")


# ── Title fetching (separated for easy mocking) ──────────────────────

class _TitleParser(HTMLParser):
    """Minimal HTML parser that extracts the <title> text."""

    def __init__(self) -> None:
        super().__init__()
        self._in_title = False
        self.title = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data


def fetch_title(url: str) -> str:
    """Fetch the <title> of a web page. Returns empty string on failure.

    This function is intentionally separated to be easily mockable in tests.
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "bmk/0.1"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read(64_000).decode("utf-8", errors="replace")
        parser = _TitleParser()
        parser.feed(html)
        return parser.title.strip()
    except Exception:
        return ""


def _validate_url(url: str) -> str:
    """Validate and return the URL, or exit with an error."""
    if not _URL_RE.match(url):
        print(f"Error: Invalid URL: {url}", file=sys.stderr)
        sys.exit(1)
    return url


# ── CLI commands ──────────────────────────────────────────────────────

def cmd_add(args: argparse.Namespace, db_path: Path) -> None:
    """Add a new bookmark."""
    url = _validate_url(args.url)
    title = args.title or fetch_title(url)
    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
    bm = Bookmark(url=url, title=title, tags=tags, description=args.desc or "")

    conn = get_connection(db_path)
    try:
        bm_id = add_bookmark(conn, bm)
        print(f"Added bookmark #{bm_id}: {bm.title or bm.url}")
    except sqlite3.IntegrityError:
        print(f"Error: URL already exists: {url}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


def cmd_list(args: argparse.Namespace, db_path: Path) -> None:
    """List bookmarks with optional filters."""
    conn = get_connection(db_path)
    try:
        bookmarks = list_bookmarks(conn, tag=args.tag, limit=args.limit, sort=args.sort)
        if not bookmarks:
            print("No bookmarks found.")
            return
        for bm in bookmarks:
            tags_str = f" [{bm.tags_csv}]" if bm.tags else ""
            print(f"  #{bm.id}  {bm.title or bm.url}{tags_str}")
            print(f"       {bm.url}")
    finally:
        conn.close()


def cmd_search(args: argparse.Namespace, db_path: Path) -> None:
    """Search bookmarks with fuzzy matching."""
    conn = get_connection(db_path)
    try:
        all_bms = get_all_bookmarks(conn)
        results = fuzzy_search(all_bms, args.query)
        if not results:
            print("No matching bookmarks found.")
            return
        for bm in results:
            tags_str = f" [{bm.tags_csv}]" if bm.tags else ""
            print(f"  #{bm.id}  {bm.title or bm.url}{tags_str}")
            print(f"       {bm.url}")
    finally:
        conn.close()


def cmd_delete(args: argparse.Namespace, db_path: Path) -> None:
    """Delete a bookmark by id."""
    conn = get_connection(db_path)
    try:
        if delete_bookmark(conn, id=args.id):
            print(f"Deleted bookmark #{args.id}.")
        else:
            print(f"Error: Bookmark #{args.id} not found.", file=sys.stderr)
            sys.exit(1)
    finally:
        conn.close()


def cmd_edit(args: argparse.Namespace, db_path: Path) -> None:
    """Edit an existing bookmark."""
    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None
    conn = get_connection(db_path)
    try:
        if edit_bookmark(conn, id=args.id, title=args.title, tags=tags, description=args.desc):
            print(f"Updated bookmark #{args.id}.")
        else:
            print(f"Error: Bookmark #{args.id} not found or no changes.", file=sys.stderr)
            sys.exit(1)
    finally:
        conn.close()


def cmd_tags(args: argparse.Namespace, db_path: Path) -> None:
    """List all tags with counts."""
    conn = get_connection(db_path)
    try:
        tag_counts = all_tags_with_counts(conn)
        if not tag_counts:
            print("No tags found.")
            return
        for tag, count in tag_counts:
            print(f"  {tag} ({count})")
    finally:
        conn.close()


def cmd_export(args: argparse.Namespace, db_path: Path) -> None:
    """Export bookmarks to a file or stdout."""
    conn = get_connection(db_path)
    try:
        bookmarks = get_all_bookmarks(conn)
        content = export_bookmarks(bookmarks, fmt=args.format, output=args.output)
        if not args.output:
            print(content)
        else:
            print(f"Exported {len(bookmarks)} bookmarks to {args.output}")
    finally:
        conn.close()


def cmd_import(args: argparse.Namespace, db_path: Path) -> None:
    """Import bookmarks from a file."""
    try:
        bookmarks = import_bookmarks(args.file, fmt=args.format)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    conn = get_connection(db_path)
    added = 0
    skipped = 0
    try:
        for bm in bookmarks:
            try:
                add_bookmark(conn, bm)
                added += 1
            except sqlite3.IntegrityError:
                skipped += 1
        print(f"Imported {added} bookmarks ({skipped} duplicates skipped).")
    finally:
        conn.close()


def cmd_stats(args: argparse.Namespace, db_path: Path) -> None:
    """Show bookmark statistics."""
    conn = get_connection(db_path)
    try:
        stats = get_stats(conn)
        print(f"Total bookmarks: {stats['total_bookmarks']}")
        print(f"Unique tags:     {stats['unique_tags']}")
    finally:
        conn.close()


# ── Argument parser ───────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(prog="bmk", description="CLI bookmark manager")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to database file")
    sub = parser.add_subparsers(dest="command")

    # add
    p_add = sub.add_parser("add", help="Add a bookmark")
    p_add.add_argument("url")
    p_add.add_argument("--title", "-t")
    p_add.add_argument("--tags", "-T")
    p_add.add_argument("--desc", "-d")

    # list
    p_list = sub.add_parser("list", help="List bookmarks")
    p_list.add_argument("--tag")
    p_list.add_argument("--limit", type=int)
    p_list.add_argument("--sort", choices=["date", "title"], default="date")

    # search
    p_search = sub.add_parser("search", help="Fuzzy search bookmarks")
    p_search.add_argument("query")

    # delete
    p_del = sub.add_parser("delete", help="Delete a bookmark")
    p_del.add_argument("id", type=int)

    # edit
    p_edit = sub.add_parser("edit", help="Edit a bookmark")
    p_edit.add_argument("id", type=int)
    p_edit.add_argument("--title", "-t")
    p_edit.add_argument("--tags", "-T")
    p_edit.add_argument("--desc", "-d")

    # tags
    sub.add_parser("tags", help="List all tags with counts")

    # export
    p_export = sub.add_parser("export", help="Export bookmarks")
    p_export.add_argument("--format", "-f", choices=["json", "csv", "html"], default="json")
    p_export.add_argument("--output", "-o")

    # import
    p_import = sub.add_parser("import", help="Import bookmarks")
    p_import.add_argument("file")
    p_import.add_argument("--format", "-f", choices=["json", "csv"])

    # stats
    sub.add_parser("stats", help="Show statistics")

    return parser


def main() -> None:
    """Main entry point for the bmk CLI."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    commands: dict[str, type[...]] = {
        "add": cmd_add,
        "list": cmd_list,
        "search": cmd_search,
        "delete": cmd_delete,
        "edit": cmd_edit,
        "tags": cmd_tags,
        "export": cmd_export,
        "import": cmd_import,
        "stats": cmd_stats,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args, args.db)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
