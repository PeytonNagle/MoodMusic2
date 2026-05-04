"""
MoodMusic2 Flask application.

This module initializes the Flask app, configures services, and registers blueprints.
"""

from flask import Flask
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix
import logging
import os
import signal
import sys
from config import Config
from services.service_factory import MoodServiceFactory
from services.music_service_factory import MusicServiceFactory
from workers import SaveWorker
from blueprints import register_blueprints
import db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Trust X-Forwarded-* from one proxy hop (Railway's gateway) so rate limiting
# keys on the real client IP, not the gateway.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Lock CORS to an allowlist from env (comma-separated). Falls back to localhost
# for dev. Set CORS_ALLOWED_ORIGINS=https://your-frontend.up.railway.app on Railway.
_allowed_origins = [
    o.strip()
    for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if o.strip()
] or ["http://localhost:3000"]
CORS(
    app,
    resources={r"/api/*": {"origins": _allowed_origins}},
    supports_credentials=False,
)
logger.info(f"CORS allowed origins: {_allowed_origins}")

# Per-IP rate limiter. In-memory storage is fine for the single-instance demo;
# scale to Redis (storage_uri="redis://...") if running multiple workers.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200/day", "60/hour"],
    headers_enabled=True,
)

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

# Initialize music enrichment provider via factory
music_provider = Config.get_music_provider()
logger.info(f"Initializing music provider: {music_provider}")
music_service = MusicServiceFactory.create_service(
    provider=music_provider,
    spotify_client_id=Config.SPOTIPY_CLIENT_ID,
    spotify_client_secret=Config.SPOTIPY_CLIENT_SECRET,
    spotify_config=Config._config_data.get('music_provider', {}).get('spotify'),
    itunes_config=Config._config_data.get('music_provider', {}).get('itunes'),
)

if not music_service:
    logger.error(f"Failed to initialize music provider: {music_provider}")

# Initialize background worker for async DB saves
save_worker = SaveWorker()
save_worker.start()

# Register all blueprints
register_blueprints(
    app,
    mood_service=mood_service,
    music_service=music_service,
    save_queue=save_worker.queue,
    limiter=limiter,
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
