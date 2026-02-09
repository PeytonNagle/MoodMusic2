"""Health controller handling health check and root endpoints."""

import logging
from flask import jsonify
from config import Config
from .base_controller import BaseController

logger = logging.getLogger(__name__)


class HealthController(BaseController):
    """Controller for health check and informational endpoints."""

    def __init__(self, mood_service=None, spotify_service=None):
        """
        Initialize health controller.

        Args:
            mood_service: Optional AI mood service instance (BaseMoodService)
            spotify_service: Optional SpotifyService instance
        """
        super().__init__()
        self.mood_service = mood_service
        self.spotify_service = spotify_service

    def health_check(self):
        """Health check endpoint."""
        try:
            # Get active AI provider
            ai_provider = Config.get_ai_provider()

            # Test AI service connection
            ai_status = self.mood_service.test_connection() if self.mood_service else False

            # Test Spotify connection
            spotify_status = self.spotify_service.test_connection() if self.spotify_service else False

            return jsonify({
                'status': 'healthy',
                'services': {
                    'ai_provider': ai_provider,
                    'ai_service': 'connected' if ai_status else 'disconnected',
                    'spotify': 'connected' if spotify_status else 'disconnected'
                },
                'config_loaded': Config.validate_config()
            })

        except Exception as e:
            logger.exception("Health check failed")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e)
            }), 500

    def root(self):
        """Root endpoint."""
        return jsonify({
            'message': 'Text-to-Spotify API',
            'version': '1.0.0',
            'endpoints': {
                'search': '/api/search (POST)',
                'health': '/api/health (GET)'
            }
        })
