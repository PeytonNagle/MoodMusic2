"""
Abstract base class for mood analysis and song recommendation services.

This module defines the interface contract that all AI provider implementations
must follow (GeminiService, OllamaService, etc.).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseMoodService(ABC):
    """Abstract base class for mood analysis and song recommendation services."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the mood service with optional configuration.

        Args:
            config: Configuration dictionary with provider-specific settings
        """
        self.config = config or {}

    @abstractmethod
    def analyze_mood(
        self,
        text_description: str,
        emojis: Optional[List[str]] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze mood from text description and emojis.

        Args:
            text_description: User's mood description
            emojis: Optional list of emoji characters
            model: Optional model identifier to override default

        Returns:
            Dict with structure: {"analysis": {"mood": "...", "matched_criteria": [...]}}
        """
        pass

    @abstractmethod
    def recommend_songs(
        self,
        text_description: str,
        analysis: Dict[str, Any],
        num_songs: int = 10,
        emojis: Optional[List[str]] = None,
        model: Optional[str] = None,
        min_popularity: Optional[int] = None,
        popularity_label: Optional[str] = None,
        token_cap: int = 12000
    ) -> Dict[str, Any]:
        """
        Recommend songs based on mood analysis.

        Args:
            text_description: User's mood description
            analysis: Mood analysis result from analyze_mood()
            num_songs: Number of songs to recommend
            emojis: Optional list of emoji characters
            model: Optional model identifier to override default
            min_popularity: Minimum Spotify popularity score (0-100)
            popularity_label: Human-readable popularity category
            token_cap: Maximum tokens for response

        Returns:
            Dict with structure: {"songs": [{"title": "...", "artist": "...", "why": "...", "matched_criteria": [...]}, ...]}
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test if the service is available and responding.

        Returns:
            True if service is reachable, False otherwise
        """
        pass

    def get_song_suggestions(
        self,
        text_description: str,
        num_songs: int = 10,
        emojis: Optional[List[str]] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Backward-compatible orchestrator method that combines analysis and recommendations.

        This method maintains compatibility with legacy code that expects a single call
        to get both analysis and song recommendations.

        Args:
            text_description: User's mood description
            num_songs: Number of songs to recommend
            emojis: Optional list of emoji characters
            model: Optional model identifier to override default

        Returns:
            Dict with structure: {
                "analysis": {"mood": "...", "matched_criteria": [...]},
                "songs": [{"title": "...", "artist": "...", ...}, ...]
            }
        """
        analysis_result = self.analyze_mood(text_description, emojis, model)
        songs_result = self.recommend_songs(
            text_description,
            analysis_result.get("analysis", {}),
            num_songs,
            emojis,
            model
        )
        return {
            "analysis": analysis_result.get("analysis", {}),
            "songs": songs_result.get("songs", [])
        }
