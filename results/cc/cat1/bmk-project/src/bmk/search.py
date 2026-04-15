"""Fuzzy search for bookmarks using difflib."""

from __future__ import annotations

from difflib import SequenceMatcher

from bmk.models import Bookmark


def _ratio(a: str, b: str) -> float:
    """Return similarity ratio between two strings (case-insensitive)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def fuzzy_search(bookmarks: list[Bookmark], query: str, *, threshold: float = 0.3) -> list[Bookmark]:
    """Search bookmarks by fuzzy-matching query against title, URL, tags, and description.

    Returns bookmarks sorted by best match score (descending), filtered by threshold.
    """
    scored: list[tuple[float, Bookmark]] = []

    for bm in bookmarks:
        scores = [
            _ratio(query, bm.title),
            _ratio(query, bm.url),
            _ratio(query, bm.description),
        ]
        for tag in bm.tags:
            scores.append(_ratio(query, tag))

        # Also check substring containment for better UX
        text = f"{bm.title} {bm.url} {bm.description} {' '.join(bm.tags)}".lower()
        if query.lower() in text:
            scores.append(0.9)

        best = max(scores) if scores else 0.0
        if best >= threshold:
            scored.append((best, bm))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [bm for _, bm in scored]
