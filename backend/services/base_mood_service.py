"""
Abstract base class for mood analysis and song recommendation services.

This module defines the interface contract that all AI provider implementations
must follow (GeminiService, OllamaService, etc.).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)


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

    def _extract_json(self, content: str) -> Any:
        """Normalize and parse JSON, stripping markdown code fences if present."""
        content = content.strip()
        if content.startswith('```json'):
            content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
        elif content.startswith('```'):
            content = content[3:]
            if content.endswith('```'):
                content = content[:-3]
        return json.loads(content.strip())

    def _extract_json_with_salvage(self, content: str) -> Any:
        """Parse JSON and attempt a light repair on failure."""
        try:
            return self._extract_json(content)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse failed; trimming to last complete song. error={e}")
            repaired = self._salvage_to_last_complete_song(content)
            parsed = self._extract_json(repaired)
            logger.info("JSON salvage succeeded using trimmed payload.")
            return parsed

    def _salvage_to_last_complete_song(self, content: str) -> str:
        """Trim a truncated response back to the last complete song object and close the JSON."""
        text = content.strip()
        if text.startswith('```json'):
            text = text[7:]
            if text.endswith('```'):
                text = text[:-3]
        elif text.startswith('```'):
            text = text[3:]
            if text.endswith('```'):
                text = text[:-3]

        text = text.strip()

        last_brace = text.rfind('}')
        if last_brace == -1:
            return text

        text = text[: last_brace + 1]
        text = text.rstrip(', \n\r\t')

        if text.endswith(','):
            text = text.rstrip(', \n\r\t')

        if '"songs"' in text and '[' in text and not text.strip().endswith((']', ']}', '}}')):
            text += "\n  ]\n}"

        return text
