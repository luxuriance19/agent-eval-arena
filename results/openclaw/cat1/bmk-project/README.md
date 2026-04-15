# bmk - Bookmark Manager

A Python CLI bookmark manager with SQLite storage, fuzzy search, and import/export functionality.

## Installation

```bash
pip install -e .
```

## Usage

### Add a bookmark
```bash
bmk add https://example.com --title "Example" --tags "demo,test" --desc "A test site"
```

### List bookmarks
```bash
bmk list
bmk list --tag python --limit 10 --sort title
```

### Search bookmarks
```bash
bmk search python
```

### Delete a bookmark
```bash
bmk delete 1
```

### Edit a bookmark
```bash
bmk edit 1 --title "New Title" --tags "new,tags"
```

### List all tags
```bash
bmk tags
```

### Export bookmarks
```bash
bmk export --format json --output bookmarks.json
bmk export --format csv --output bookmarks.csv
bmk export --format html --output bookmarks.html
```

### Import bookmarks
```bash
bmk import bookmarks.json --format json
bmk import bookmarks.csv --format csv
```

### Show statistics
```bash
bmk stats
```

## Testing

```bash
pytest tests/ -v
```

## Features

- SQLite database storage at `~/.bmk/bookmarks.db`
- Auto-fetch page titles when not provided
- Fuzzy search using difflib
- Tag system with counts
- Import/export to JSON, CSV, and HTML
- Type annotations on all functions
- Comprehensive error handling
