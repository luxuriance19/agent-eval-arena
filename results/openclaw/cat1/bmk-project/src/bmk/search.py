"""Fuzzy search functionality."""
from difflib import SequenceMatcher
from typing import List
from .models import Bookmark


def fuzzy_search(bookmarks: List[Bookmark], query: str, threshold: float = 0.3) -> List[Bookmark]:
    """
    Perform fuzzy search on bookmarks using difflib.
    
    Args:
        bookmarks: List of bookmarks to search
        query: Search query string
        threshold: Minimum similarity ratio (0.0 to 1.0)
    
    Returns:
        List of bookmarks sorted by relevance
    """
    results = []
    query_lower = query.lower()
    
    for bookmark in bookmarks:
        # Calculate similarity scores for different fields
        title_score = SequenceMatcher(None, query_lower, bookmark.title.lower()).ratio()
        url_score = SequenceMatcher(None, query_lower, bookmark.url.lower()).ratio()
        desc_score = SequenceMatcher(None, query_lower, bookmark.description.lower()).ratio()
        
        # Check tags
        tag_score = 0.0
        for tag in bookmark.tags:
            tag_score = max(tag_score, SequenceMatcher(None, query_lower, tag.lower()).ratio())
        
        # Use the highest score
        max_score = max(title_score, url_score, desc_score, tag_score)
        
        if max_score >= threshold:
            results.append((max_score, bookmark))
    
    # Sort by score descending
    results.sort(key=lambda x: x[0], reverse=True)
    
    return [bookmark for _, bookmark in results]
