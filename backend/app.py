"""
MoodMusic2 Flask application.

This module initializes the Flask app, configures services, and registers blueprints.
"""

from flask import Flask
from flask_cors import CORS
import logging
import os
from config import Config
from services.gemini_service import GeminiService
from services.spotify_service import SpotifyService
from workers import SaveWorker
from blueprints import register_blueprints

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Validate configuration
if not Config.validate_config():
    logger.warning("Some configuration variables are missing. Please check your .env file.")

# Initialize services with config injection
gemini_service = GeminiService(
    Config.GEMINI_API_KEY,
    Config._config_data.get('gemini')
) if Config.GEMINI_API_KEY else None

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
    gemini_service=gemini_service,
    spotify_service=spotify_service,
    save_queue=save_worker.queue
)

if __name__ == '__main__':
    logger.info("Starting Text-to-Spotify API server...")
    app.run(
        debug=Config.DEBUG,
        host=Config.get('flask.host', '0.0.0.0'),
        port=Config.get('flask.port', int(os.getenv('PORT', 5000)))
    )
