from __future__ import annotations

from difflib import SequenceMatcher

from bmk.models import Bookmark


def fuzzy_match_score(query: str, text: str) -> float:
    """Return a fuzzy similarity score between query and text."""

    return SequenceMatcher(None, query.lower(), text.lower()).ratio()


def score_bookmark(query: str, bookmark: Bookmark) -> float:
    """Return the best fuzzy score across bookmark fields."""

    haystacks = [bookmark.title, bookmark.url, bookmark.desc or "", " ".join(bookmark.tags)]
    return max(fuzzy_match_score(query, value) for value in haystacks)


def search_bookmarks(query: str, bookmarks: list[Bookmark], threshold: float = 0.25) -> list[Bookmark]:
    """Return bookmarks sorted by fuzzy match score."""

    scored: list[tuple[float, Bookmark]] = []
    for bookmark in bookmarks:
        score = score_bookmark(query, bookmark)
        if score >= threshold:
            scored.append((score, bookmark))
    scored.sort(key=lambda item: (-item[0], item[1].title.lower()))
    return [bookmark for _, bookmark in scored]
