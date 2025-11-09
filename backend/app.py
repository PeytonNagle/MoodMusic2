from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import os
from config import Config
from services.gemini_service import GeminiService
from services.spotify_service import SpotifyService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Validate configuration
if not Config.validate_config():
    logger.warning("Some configuration variables are missing. Please check your .env file.")

# Initialize services
gemini_service = GeminiService(Config.GEMINI_API_KEY) if Config.GEMINI_API_KEY else None
spotify_service = SpotifyService(Config.SPOTIPY_CLIENT_ID, Config.SPOTIPY_CLIENT_SECRET) if Config.SPOTIPY_CLIENT_ID and Config.SPOTIPY_CLIENT_SECRET else None

@app.route('/api/search', methods=['POST'])
def search_music():
    """
    Search for music based on text description
    
    Expected JSON payload:
    {
        "query": "upbeat indie rock for a road trip",
        "limit": 10  # optional, defaults to 10
    }
    
    Returns:
    {
        "success": true,
        "songs": [
            {
                "id": "spotify_track_id",
                "title": "Song Title",
                "artist": "Artist Name",
                "album": "Album Name",
                "album_art": "https://...",
                "preview_url": "https://...",
                "spotify_url": "https://...",
                "release_year": "2023",
                "duration_formatted": "3:45"
            }
        ],
        "error": null
    }
    """
    try:
        # Validate request
        if not request.is_json:
            return jsonify({
                'success': False,
                'songs': [],
                'error': 'Request must be JSON'
            }), 400
        
        data = request.get_json()
        
        if not data or 'query' not in data:
            return jsonify({
                'success': False,
                'songs': [],
                'error': 'Missing required field: query'
            }), 400
        
        query = data['query'].strip()
        limit = data.get('limit', 10)
        
        if not query:
            return jsonify({
                'success': False,
                'songs': [],
                'error': 'Query cannot be empty'
            }), 400
        
        # Validate limit
        try:
            limit = int(limit)
            if limit < 1 or limit > 50:
                limit = 10
        except (ValueError, TypeError):
            limit = 10
        
        logger.info(f"Processing search query: '{query}' with limit: {limit}")
        
        # Check if services are available
        if not gemini_service:
            return jsonify({
                'success': False,
                'songs': [],
                'error': 'Gemini service not configured. Please add GEMINI_API_KEY to .env file.'
            }), 500
        
        if not spotify_service:
            return jsonify({
                'success': False,
                'songs': [],
                'error': 'Spotify service not configured. Please add SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET to .env file.'
            }), 500
        
        # Step 1: Get song suggestions from Gemini
        logger.info("Getting song suggestions from Gemini...")
        suggestions_result = gemini_service.get_song_suggestions(query, limit)
        songs_from_ai = suggestions_result.get('songs', []) if isinstance(suggestions_result, dict) else suggestions_result
        analysis = suggestions_result.get('analysis', {}) if isinstance(suggestions_result, dict) else {}

        if not songs_from_ai:
            return jsonify({
                'success': False,
                'songs': [],
                'error': 'No songs found for the given query'
            }), 404

        # Step 2: Enrich songs with Spotify data
        logger.info("Enriching songs with Spotify data...")
        enriched_songs = spotify_service.enrich_songs(songs_from_ai)
        
        # Filter out songs without preview URLs (optional)
        songs_with_previews = [song for song in enriched_songs if song.get('preview_url')]
        
        logger.info(f"Found {len(enriched_songs)} total songs, {len(songs_with_previews)} with previews")
        
        return jsonify({
            'success': True,
            'songs': enriched_songs,  # Return all songs, not just those with previews
            'analysis': analysis,
            'error': None
        })
        
    except Exception as e:
        logger.error(f"Error processing search request: {e}")
        return jsonify({
            'success': False,
            'songs': [],
            'error': f'Internal server error: {str(e)}'
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test Gemini connection
        gemini_status = gemini_service.test_connection() if gemini_service else False
        
        # Test Spotify connection
        spotify_status = spotify_service.test_connection() if spotify_service else False
        
        return jsonify({
            'status': 'healthy',
            'services': {
                'gemini': 'connected' if gemini_status else 'disconnected',
                'spotify': 'connected' if spotify_status else 'disconnected'
            },
            'config_loaded': Config.validate_config()
        })
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

@app.route('/', methods=['GET'])
def root():
    """Root endpoint"""
    return jsonify({
        'message': 'Text-to-Spotify API',
        'version': '1.0.0',
        'endpoints': {
            'search': '/api/search (POST)',
            'health': '/api/health (GET)'
        }
    })

if __name__ == '__main__':
    logger.info("Starting Text-to-Spotify API server...")
    app.run(debug=Config.DEBUG, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))



