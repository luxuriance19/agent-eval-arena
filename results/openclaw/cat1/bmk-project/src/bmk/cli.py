"""Command-line interface for bookmark manager."""
import sys
import argparse
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from .db import BookmarkDB
from .search import fuzzy_search
from .io import export_json, export_csv, export_html, import_json, import_csv


def fetch_page_title(url: str) -> str:
    """
    Fetch page title from URL.
    
    This function is separated for easy mocking in tests.
    In production, this would use urllib or requests.
    """
    try:
        from urllib.request import urlopen, Request
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=5) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
            # Simple title extraction
            start = html.find('<title>')
            end = html.find('</title>')
            if start != -1 and end != -1:
                return html[start + 7:end].strip()
    except Exception:
        pass
    
    return url


def validate_url(url: str) -> bool:
    """Validate URL format."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def cmd_add(args: argparse.Namespace, db: BookmarkDB) -> None:
    """Handle add command."""
    url = args.url
    
    if not validate_url(url):
        print(f"Error: Invalid URL: {url}", file=sys.stderr)
        sys.exit(1)
    
    if db.url_exists(url):
        print(f"Error: URL already exists: {url}", file=sys.stderr)
        sys.exit(1)
    
    title = args.title if args.title else fetch_page_title(url)
    tags = args.tags.split(",") if args.tags else []
    tags = [tag.strip() for tag in tags if tag.strip()]
    description = args.desc or ""
    
    try:
        bookmark_id = db.add_bookmark(url, title, tags, description)
        print(f"Added bookmark #{bookmark_id}: {title}")
    except Exception as e:
        print(f"Error adding bookmark: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_list(args: argparse.Namespace, db: BookmarkDB) -> None:
    """Handle list command."""
    bookmarks = db.get_all_bookmarks(
        tag=args.tag,
        limit=args.limit,
        sort_by=args.sort
    )
    
    if not bookmarks:
        print("No bookmarks found.")
        return
    
    for bm in bookmarks:
        tags_str = f" [{', '.join(bm.tags)}]" if bm.tags else ""
        print(f"#{bm.id}: {bm.title}{tags_str}")
        print(f"  URL: {bm.url}")
        if bm.description:
            print(f"  Description: {bm.description}")
        print(f"  Added: {bm.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print()


def cmd_search(args: argparse.Namespace, db: BookmarkDB) -> None:
    """Handle search command."""
    # First get basic SQL search results
    bookmarks = db.search_bookmarks(args.query)
    
    # Apply fuzzy search
    results = fuzzy_search(bookmarks, args.query)
    
    if not results:
        print("No matches found.")
        return
    
    print(f"Found {len(results)} result(s):")
    for bm in results:
        tags_str = f" [{', '.join(bm.tags)}]" if bm.tags else ""
        print(f"#{bm.id}: {bm.title}{tags_str}")
        print(f"  URL: {bm.url}")
        if bm.description:
            print(f"  Description: {bm.description}")
        print()


def cmd_delete(args: argparse.Namespace, db: BookmarkDB) -> None:
    """Handle delete command."""
    if db.delete_bookmark(args.id):
        print(f"Deleted bookmark #{args.id}")
    else:
        print(f"Error: Bookmark #{args.id} not found", file=sys.stderr)
        sys.exit(1)


def cmd_edit(args: argparse.Namespace, db: BookmarkDB) -> None:
    """Handle edit command."""
    tags = None
    if args.tags is not None:
        tags = args.tags.split(",")
        tags = [tag.strip() for tag in tags if tag.strip()]
    
    if db.update_bookmark(args.id, title=args.title, tags=tags, description=args.desc):
        print(f"Updated bookmark #{args.id}")
    else:
        print(f"Error: Bookmark #{args.id} not found or no changes made", file=sys.stderr)
        sys.exit(1)


def cmd_tags(args: argparse.Namespace, db: BookmarkDB) -> None:
    """Handle tags command."""
    tags = db.get_all_tags()
    
    if not tags:
        print("No tags found.")
        return
    
    print("Tags:")
    for tag, count in sorted(tags.items(), key=lambda x: x[1], reverse=True):
        print(f"  {tag}: {count}")


def cmd_export(args: argparse.Namespace, db: BookmarkDB) -> None:
    """Handle export command."""
    bookmarks = db.get_all_bookmarks()
    
    if not bookmarks:
        print("No bookmarks to export.")
        return
    
    output_path = Path(args.output) if args.output else Path(f"bookmarks.{args.format}")
    
    try:
        if args.format == "json":
            export_json(bookmarks, output_path)
        elif args.format == "csv":
            export_csv(bookmarks, output_path)
        elif args.format == "html":
            export_html(bookmarks, output_path)
        
        print(f"Exported {len(bookmarks)} bookmark(s) to {output_path}")
    except Exception as e:
        print(f"Error exporting: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_import(args: argparse.Namespace, db: BookmarkDB) -> None:
    """Handle import command."""
    file_path = Path(args.file)
    
    if not file_path.exists():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    
    try:
        if args.format == "json":
            bookmarks = import_json(file_path)
        elif args.format == "csv":
            bookmarks = import_csv(file_path)
        else:
            print(f"Error: Unsupported format: {args.format}", file=sys.stderr)
            sys.exit(1)
        
        added = 0
        skipped = 0
        
        for bm_data in bookmarks:
            if db.url_exists(bm_data["url"]):
                skipped += 1
                continue
            
            db.add_bookmark(
                bm_data["url"],
                bm_data["title"],
                bm_data["tags"],
                bm_data["description"]
            )
            added += 1
        
        print(f"Imported {added} bookmark(s), skipped {skipped} duplicate(s)")
    except Exception as e:
        print(f"Error importing: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_stats(args: argparse.Namespace, db: BookmarkDB) -> None:
    """Handle stats command."""
    stats = db.get_stats()
    print(f"Total bookmarks: {stats['total_bookmarks']}")
    print(f"Unique tags: {stats['unique_tags']}")


def main() -> None:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(description="bmk - Bookmark Manager")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Add command
    add_parser = subparsers.add_parser("add", help="Add a bookmark")
    add_parser.add_argument("url", help="URL to bookmark")
    add_parser.add_argument("--title", help="Title (auto-fetched if not provided)")
    add_parser.add_argument("--tags", help="Comma-separated tags")
    add_parser.add_argument("--desc", help="Description")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List bookmarks")
    list_parser.add_argument("--tag", help="Filter by tag")
    list_parser.add_argument("--limit", type=int, help="Limit results")
    list_parser.add_argument("--sort", choices=["date", "title"], default="date", help="Sort order")
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search bookmarks")
    search_parser.add_argument("query", help="Search query")
    
    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a bookmark")
    delete_parser.add_argument("id", type=int, help="Bookmark ID")
    
    # Edit command
    edit_parser = subparsers.add_parser("edit", help="Edit a bookmark")
    edit_parser.add_argument("id", type=int, help="Bookmark ID")
    edit_parser.add_argument("--title", help="New title")
    edit_parser.add_argument("--tags", help="New comma-separated tags")
    edit_parser.add_argument("--desc", help="New description")
    
    # Tags command
    subparsers.add_parser("tags", help="List all tags")
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export bookmarks")
    export_parser.add_argument("--format", choices=["json", "csv", "html"], default="json", help="Export format")
    export_parser.add_argument("--output", help="Output file path")
    
    # Import command
    import_parser = subparsers.add_parser("import", help="Import bookmarks")
    import_parser.add_argument("file", help="File to import")
    import_parser.add_argument("--format", choices=["json", "csv"], default="json", help="Import format")
    
    # Stats command
    subparsers.add_parser("stats", help="Show statistics")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    db = BookmarkDB()
    
    commands = {
        "add": cmd_add,
        "list": cmd_list,
        "search": cmd_search,
        "delete": cmd_delete,
        "edit": cmd_edit,
        "tags": cmd_tags,
        "export": cmd_export,
        "import": cmd_import,
        "stats": cmd_stats
    }
    
    commands[args.command](args, db)


if __name__ == "__main__":
    main()
