"""Data models for bookmarks."""
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


@dataclass
class Bookmark:
    """Represents a bookmark entry."""
    id: Optional[int]
    url: str
    title: str
    tags: List[str]
    description: str
    created_at: datetime
    
    def tags_str(self) -> str:
        """Convert tags list to comma-separated string."""
        return ",".join(self.tags) if self.tags else ""
    
    @staticmethod
    def parse_tags(tags_str: str) -> List[str]:
        """Parse comma-separated tags string into list."""
        if not tags_str:
            return []
        return [tag.strip() for tag in tags_str.split(",") if tag.strip()]
