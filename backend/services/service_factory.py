"""
Factory for creating mood analysis service instances.

This module provides a factory pattern for instantiating the appropriate
AI provider service based on configuration.
"""

import logging
from typing import Optional, Dict, Any
from .base_mood_service import BaseMoodService
from .gemini_service import GeminiService
from .ollama_service import OllamaService

logger = logging.getLogger(__name__)


class MoodServiceFactory:
    """Factory for creating mood analysis service instances."""

    @staticmethod
    def create_service(
        provider: str,
        gemini_api_key: Optional[str] = None,
        gemini_config: Optional[Dict[str, Any]] = None,
        ollama_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[BaseMoodService]:
        """
        Create a mood service instance based on provider name.

        Args:
            provider: 'gemini' or 'ollama'
            gemini_api_key: API key for Gemini (required if provider='gemini')
            gemini_config: Configuration dict for GeminiService
            ollama_config: Configuration dict for OllamaService

        Returns:
            BaseMoodService instance or None if provider cannot be initialized

        Raises:
            ValueError: If provider name is not recognized
        """
        provider = provider.lower().strip()

        if provider == 'gemini':
            if not gemini_api_key:
                logger.error("Gemini provider selected but GEMINI_API_KEY not set")
                return None
            logger.info("Creating GeminiService instance")
            return GeminiService(gemini_api_key, gemini_config)

        elif provider == 'ollama':
            logger.info("Creating OllamaService instance")
            return OllamaService(ollama_config)

        else:
            raise ValueError(
                f"Unknown AI provider: {provider}. Must be 'gemini' or 'ollama'."
            )
