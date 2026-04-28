"""Factory for creating music enrichment provider instances."""

import logging
from typing import Any, Dict, Optional

from .base_music_service import BaseMusicService
from .itunes_service import ItunesService
from .spotify_service import SpotifyService

logger = logging.getLogger(__name__)


class MusicServiceFactory:
    """Create a music enrichment service based on configured provider name."""

    @staticmethod
    def create_service(
        provider: str,
        spotify_client_id: Optional[str] = None,
        spotify_client_secret: Optional[str] = None,
        spotify_config: Optional[Dict[str, Any]] = None,
        itunes_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[BaseMusicService]:
        provider = (provider or "").lower().strip()

        if provider == "itunes":
            logger.info("Creating ItunesService instance")
            return ItunesService(itunes_config)

        if provider == "spotify":
            if not (spotify_client_id and spotify_client_secret):
                logger.error("Spotify provider selected but Spotify credentials are not set")
                return None
            logger.info("Creating SpotifyService instance")
            return SpotifyService(spotify_client_id, spotify_client_secret, spotify_config)

        raise ValueError(f"Unknown music provider: {provider}. Must be 'itunes' or 'spotify'.")
