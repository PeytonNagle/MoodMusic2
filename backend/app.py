"""
MoodMusic2 Flask application.

This module initializes the Flask app, configures services, and registers blueprints.
"""

from flask import Flask
from flask_cors import CORS
import logging
import os
import signal
import sys
from config import Config
from services.service_factory import MoodServiceFactory
from services.spotify_service import SpotifyService
from workers import SaveWorker
from blueprints import register_blueprints
import db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Validate configuration
if not Config.validate_config():
    logger.warning("Some configuration variables are missing. Please check your .env file.")

# Initialize AI provider service with config-driven factory
provider = Config.get_ai_provider()
logger.info(f"Initializing AI provider: {provider}")

# Override base_url if environment variable is set
ollama_config = Config._config_data.get('ai_provider', {}).get('ollama', {})
if Config.OLLAMA_BASE_URL:
    ollama_config = {**ollama_config, 'base_url': Config.OLLAMA_BASE_URL}

mood_service = MoodServiceFactory.create_service(
    provider=provider,
    gemini_api_key=Config.GEMINI_API_KEY,
    gemini_config=Config._config_data.get('gemini'),
    ollama_config=ollama_config,
)

if not mood_service:
    logger.error(f"Failed to initialize AI provider: {provider}")

# Initialize Spotify service
spotify_service = SpotifyService(
    Config.SPOTIPY_CLIENT_ID,
    Config.SPOTIPY_CLIENT_SECRET,
    Config._config_data.get('spotify')
) if Config.SPOTIPY_CLIENT_ID and Config.SPOTIPY_CLIENT_SECRET else None

# Initialize background worker for async DB saves
save_worker = SaveWorker()
save_worker.start()

# Register all blueprints
register_blueprints(
    app,
    gemini_service=mood_service,  # Name unchanged for backward compatibility
    spotify_service=spotify_service,
    save_queue=save_worker.queue
)

# Register teardown handlers for cleanup
@app.teardown_appcontext
def shutdown_db_pool(exception=None):
    """Close database connection pool on app shutdown."""
    if exception:
        logger.error(f"App context teardown with exception: {exception}")
    db.close_pool()


# Handle shutdown signals for graceful cleanup
def signal_handler(sig, frame):
    """Handle shutdown signals for graceful cleanup."""
    logger.info(f"Received signal {sig}, shutting down gracefully...")
    save_worker.stop()
    db.close_pool()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == '__main__':
    logger.info("Starting Text-to-Spotify API server...")
    try:
        app.run(
            debug=Config.DEBUG,
            host=Config.get('flask.host', '0.0.0.0'),
            port=Config.get('flask.port', int(os.getenv('PORT', 5000)))
        )
    finally:
        # Ensure cleanup happens even if app.run() crashes
        save_worker.stop()
        db.close_pool()
