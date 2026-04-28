"""
Abstract base class for music enrichment providers.

Defines the interface that any music provider (Spotify, iTunes, ...) must implement
so that controllers and the factory can treat them interchangeably.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class BaseMusicService(ABC):
    """Abstract base class for music enrichment services."""

    @abstractmethod
    def search_track(self, title: str, artist: str) -> Optional[Dict]:
        """Search for a single track and return a normalized track payload."""
        pass

    @abstractmethod
    def enrich_songs(
        self,
        songs: List[Dict[str, str]],
        min_popularity: Optional[int] = None,
    ) -> List[Dict]:
        """Enrich a list of {title, artist, why?, matched_criteria?} dicts with provider metadata."""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Return True if the provider is reachable."""
        pass
