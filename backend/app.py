
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import os
from config import Config
from services.gemini_service import GeminiService
from db import get_connection
from services.spotify_service import SpotifyService
import psycopg2.extras
import json




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

# Popularity categories (label -> range) for filtering and Gemini hints
POPULARITY_RANGES = {
    "Any": None,
    "Global / Superstar": (90, 100),
    "Hot / Established": (75, 89),
    "Buzzing / Moderate": (50, 74),
    "Growing": (25, 49),
    "Rising": (15, 24),
    "Under the Radar": (0, 14),
}
POPULARITY_TOLERANCE = 5


def resolve_popularity_constraints(data):
    """
    Resolve popularity label/range into filtering bounds and Gemini hint.
    Supports old numeric 1-10 popularity as a fallback.
    """
    popularity_label = data.get("popularity_label")
    popularity_range = data.get("popularity_range")
    legacy_popularity = data.get("popularity", None)

    # Normalize provided label
    label_clean = None
    if isinstance(popularity_label, str):
        label_clean = popularity_label.strip()
        if not label_clean:
            label_clean = None

    # Prefer explicit range from client if valid
    range_min = range_max = None
    if isinstance(popularity_range, list) and len(popularity_range) == 2:
        try:
            range_min = int(popularity_range[0])
            range_max = int(popularity_range[1])
        except (ValueError, TypeError):
            range_min = range_max = None

    # If no explicit range, derive from label mapping
    if (range_min is None or range_max is None) and label_clean:
        mapped = POPULARITY_RANGES.get(label_clean)
        if mapped:
            range_min, range_max = mapped
        elif label_clean.lower() == "any":
            range_min = range_max = None

    # Fallback to legacy numeric (1-10 scale -> lower bound on Spotify scale)
    if range_min is None and range_max is None and legacy_popularity is not None:
        try:
            legacy_val = int(legacy_popularity)
            if 1 <= legacy_val <= 10:
                lower = (legacy_val - 1) * 10
                upper = 100
                range_min, range_max = lower, upper
        except (ValueError, TypeError):
            pass

    # Apply tolerance
    min_pop = max(0, range_min - POPULARITY_TOLERANCE) if range_min is not None else None
    max_pop = min(100, range_max + POPULARITY_TOLERANCE) if range_max is not None else None

    return {
        "popularity_label": label_clean,
        "min_popularity": min_pop,
        "max_popularity": max_pop,
    }


def filter_by_popularity(songs, min_popularity, max_popularity):
    """Filter songs list by popularity bounds if provided."""
    if min_popularity is None and max_popularity is None:
        return songs
    filtered = []
    for song in songs:
        pop = song.get("popularity", 0) if isinstance(song, dict) else 0
        if min_popularity is not None and pop < min_popularity:
            continue
        if max_popularity is not None and pop > max_popularity:
            continue
        filtered.append(song)
    return filtered

@app.route('/api/search', methods=['POST'])
def search_music():
    """
    Search for music based on text description
    
    Expected JSON payload:
    {
        "query": "upbeat indie rock for a road trip",  # optional if emojis are provided
        "emojis": ["🙂", "🔥"],  # optional, up to 12
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
        
        if not data:
            return jsonify({
                'success': False,
                'songs': [],
                'error': 'Request body is missing'
            }), 400

        query = str(data.get('query', '') or '').strip()
        limit = data.get('limit', 10)
        popularity_ctx = resolve_popularity_constraints(data)
        popularity_label = popularity_ctx["popularity_label"]
        min_popularity = popularity_ctx["min_popularity"]
        max_popularity = popularity_ctx["max_popularity"]
        emojis_raw = data.get('emojis', [])

        # Validate emojis: must be a list of strings, trimmed, deduped, and capped
        emojis = []
        if emojis_raw is not None:
            if not isinstance(emojis_raw, list):
                return jsonify({
                    'success': False,
                    'songs': [],
                    'error': 'emojis must be an array of strings'
                }), 400

            seen = set()
            for emoji in emojis_raw:
                if not isinstance(emoji, str):
                    return jsonify({
                        'success': False,
                        'songs': [],
                        'error': 'emojis must be strings'
                    }), 400
                trimmed = emoji.strip()
                if trimmed and trimmed not in seen:
                    emojis.append(trimmed)
                    seen.add(trimmed)
                if len(emojis) >= 12:
                    break

        if not query and not emojis:
            return jsonify({
                'success': False,
                'songs': [],
                'error': 'Please provide a search query or select emojis'
            }), 400
        
        # Validate limit (10-50)
        try:
            limit = int(limit)
            if limit < 10 or limit > 50:
                limit = 10
        except (ValueError, TypeError):
            limit = 10

        logger.info(
            f"Processing search query: '{query}' with limit: {limit}, popularity_label: {popularity_label}, "
            f"min_popularity: {min_popularity}, max_popularity: {max_popularity}, emojis: {emojis}"
        )
        
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
        
        # Step 1: Fast mood/constraint analysis
        logger.info("Getting mood analysis from Gemini...")
        analysis_result = gemini_service.analyze_mood(query, emojis)
        analysis = analysis_result.get('analysis', {}) if isinstance(analysis_result, dict) else {}

        # Step 2: Get song recommendations using the analysis
        # Keep requesting until we have enough songs that meet popularity criteria
        enriched_songs = []
        all_requested_songs = []  # Track all songs we've requested to avoid duplicates
        max_attempts = 5  # Maximum number of requests to avoid infinite loops
        attempt = 0
        
        while len(enriched_songs) < limit and attempt < max_attempts:
            attempt += 1
            # Request more songs than needed to account for filtering
            remaining_needed = limit - len(enriched_songs)
            request_limit = min(int(remaining_needed * 2) if remaining_needed < 25 else remaining_needed + 15, 50)
            
            logger.info(f"Attempt {attempt}: Requesting {request_limit} songs from Gemini (need {remaining_needed} more)...")
            recommendations = gemini_service.recommend_songs(
                query,
                analysis,
                request_limit,
                emojis,
                min_popularity=min_popularity,
                popularity_label=popularity_label,
            )
            songs_from_ai = recommendations.get('songs', []) if isinstance(recommendations, dict) else recommendations

            if not songs_from_ai:
                if attempt == 1:
                    return jsonify({
                        'success': False,
                        'songs': [],
                        'error': 'No songs found for the given query'
                    }), 404
                break  # No more songs available

            # Filter out songs we've already processed
            new_songs = []
            for song in songs_from_ai:
                song_key = f"{song.get('title', '').lower()}|{song.get('artist', '').lower()}"
                if song_key not in all_requested_songs:
                    new_songs.append(song)
                    all_requested_songs.append(song_key)
            
            if not new_songs:
                logger.info("No new songs to process, stopping requests")
                break

            # Enrich songs with Spotify data
            logger.info(f"Enriching {len(new_songs)} new songs with Spotify data...")
            new_enriched = spotify_service.enrich_songs(new_songs, min_popularity=min_popularity)
            enriched_songs.extend(new_enriched)
            
            logger.info(f"After attempt {attempt}: Found {len(enriched_songs)}/{limit} songs meeting criteria")

        # Limit to requested number of songs
        enriched_songs = filter_by_popularity(enriched_songs, min_popularity, max_popularity)[:limit]
        
        if len(enriched_songs) < limit:
            logger.warning(f"Could only find {len(enriched_songs)} songs meeting popularity criteria (requested {limit})")
        
        logger.info(f"Final result: {len(enriched_songs)} songs")
        
        return jsonify({
            'success': True,
            'songs': enriched_songs,
            'analysis': analysis,
            'error': None
        })
        
    except Exception as e:
        logger.exception("Error processing search request")
        return jsonify({
            'success': False,
            'songs': [],
            'error': f'Internal server error: {str(e)}'
        }), 500

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Fast mood/constraint analysis endpoint."""
    try:
        if not request.is_json:
            return jsonify({'success': False, 'analysis': {}, 'error': 'Request must be JSON'}), 400

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'analysis': {}, 'error': 'Request body is missing'}), 400

        query = str(data.get('query', '') or '').strip()
        emojis_raw = data.get('emojis', [])

        emojis = []
        if emojis_raw is not None:
            if not isinstance(emojis_raw, list):
                return jsonify({'success': False, 'analysis': {}, 'error': 'emojis must be an array of strings'}), 400
            seen = set()
            for emoji in emojis_raw:
                if not isinstance(emoji, str):
                    return jsonify({'success': False, 'analysis': {}, 'error': 'emojis must be strings'}), 400
                trimmed = emoji.strip()
                if trimmed and trimmed not in seen:
                    emojis.append(trimmed)
                    seen.add(trimmed)
                if len(emojis) >= 12:
                    break

        if not query and not emojis:
            return jsonify({'success': False, 'analysis': {}, 'error': 'Please provide a search query or select emojis'}), 400

        if not gemini_service:
            return jsonify({'success': False, 'analysis': {}, 'error': 'Gemini service not configured. Please add GEMINI_API_KEY to .env file.'}), 500

        logger.info("Getting mood analysis from Gemini (analyze endpoint)...")
        analysis_result = gemini_service.analyze_mood(query, emojis)
        analysis = analysis_result.get('analysis', {}) if isinstance(analysis_result, dict) else {}

        return jsonify({'success': True, 'analysis': analysis, 'error': None})

    except Exception as e:
        logger.exception("Error processing analyze request")
        return jsonify({'success': False, 'analysis': {}, 'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/recommend', methods=['POST'])
def recommend():
    """Recommend songs using provided analysis (or auto-analyze if missing)."""
    try:
        if not request.is_json:
            return jsonify({'success': False, 'songs': [], 'analysis': {}, 'error': 'Request must be JSON'}), 400

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'songs': [], 'analysis': {}, 'error': 'Request body is missing'}), 400

        query = str(data.get('query', '') or '').strip()
        limit = data.get('limit', 10)
        popularity_ctx = resolve_popularity_constraints(data)
        popularity_label = popularity_ctx["popularity_label"]
        min_popularity = popularity_ctx["min_popularity"]
        max_popularity = popularity_ctx["max_popularity"]
        analysis_payload = data.get('analysis', {}) or {}
        emojis_raw = data.get('emojis', [])

        emojis = []
        if emojis_raw is not None:
            if not isinstance(emojis_raw, list):
                return jsonify({'success': False, 'songs': [], 'analysis': {}, 'error': 'emojis must be an array of strings'}), 400
            seen = set()
            for emoji in emojis_raw:
                if not isinstance(emoji, str):
                    return jsonify({'success': False, 'songs': [], 'analysis': {}, 'error': 'emojis must be strings'}), 400
                trimmed = emoji.strip()
                if trimmed and trimmed not in seen:
                    emojis.append(trimmed)
                    seen.add(trimmed)
                if len(emojis) >= 12:
                    break

        if not query and not emojis:
            return jsonify({'success': False, 'songs': [], 'analysis': {}, 'error': 'Please provide a search query or select emojis'}), 400

        # Validate limit (10-50)
        try:
            limit = int(limit)
            if limit < 10 or limit > 50:
                limit = 10
        except (ValueError, TypeError):
            limit = 10

        if not gemini_service:
            return jsonify({'success': False, 'songs': [], 'analysis': {}, 'error': 'Gemini service not configured. Please add GEMINI_API_KEY to .env file.'}), 500
        if not spotify_service:
            return jsonify({'success': False, 'songs': [], 'analysis': {}, 'error': 'Spotify service not configured. Please add SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET to .env file.'}), 500

        analysis = analysis_payload if isinstance(analysis_payload, dict) else {}
        if not analysis:
            logger.info("No analysis provided; generating via Gemini...")
            analysis_result = gemini_service.analyze_mood(query, emojis)
            analysis = analysis_result.get('analysis', {}) if isinstance(analysis_result, dict) else {}

        # Keep requesting until we have enough songs that meet popularity criteria
        enriched_songs = []
        all_requested_songs = []  # Track all songs we've requested to avoid duplicates
        max_attempts = 5  # Maximum number of requests to avoid infinite loops
        attempt = 0
        
        while len(enriched_songs) < limit and attempt < max_attempts:
            attempt += 1
            # Request more songs than needed to account for filtering
            remaining_needed = limit - len(enriched_songs)
            request_limit = min(int(remaining_needed * 1.3)+1 if remaining_needed < 25 else remaining_needed + 15, 50)
            
            logger.info(f"Attempt {attempt}: Requesting {request_limit} songs from Gemini (need {remaining_needed} more)...")
            recommendations = gemini_service.recommend_songs(
                query,
                analysis,
                request_limit,
                emojis,
                min_popularity=min_popularity,
                popularity_label=popularity_label,
            )
            songs_from_ai = recommendations.get('songs', []) if isinstance(recommendations, dict) else recommendations

            if not songs_from_ai:
                if attempt == 1:
                    return jsonify({'success': False, 'songs': [], 'analysis': analysis, 'error': 'No songs found for the given query'}), 404
                break  # No more songs available

            # Filter out songs we've already processed
            new_songs = []
            for song in songs_from_ai:
                song_key = f"{song.get('title', '').lower()}|{song.get('artist', '').lower()}"
                if song_key not in all_requested_songs:
                    new_songs.append(song)
                    all_requested_songs.append(song_key)
            
            if not new_songs:
                logger.info("No new songs to process, stopping requests")
                break

            # Enrich songs with Spotify data
            logger.info(f"Enriching {len(new_songs)} new songs with Spotify data...")
            new_enriched = spotify_service.enrich_songs(new_songs, min_popularity=min_popularity)
            enriched_songs.extend(new_enriched)
            
            logger.info(f"After attempt {attempt}: Found {len(enriched_songs)}/{limit} songs meeting criteria")

        # Limit to requested number of songs
        enriched_songs = filter_by_popularity(enriched_songs, min_popularity, max_popularity)[:limit]
        
        if len(enriched_songs) < limit:
            logger.warning(f"Could only find {len(enriched_songs)} songs meeting popularity criteria (requested {limit})")

        # --- SAVE REQUEST + SONGS TO DATABASE ---
        # (these must be INSIDE the function and INSIDE the try block)
        request_id = save_user_request(query, emojis, limit, analysis)

        for i, song in enumerate(enriched_songs):
            save_recommended_song(request_id, i + 1, song)

        logger.info(f"Saved request_id={request_id} with {len(enriched_songs)} songs")

        return jsonify({'success': True, 'songs': enriched_songs, 'analysis': analysis, 'error': None})

    except Exception as e:
        logger.exception("Error processing recommend request")
        return jsonify({'success': False, 'songs': [], 'analysis': {}, 'error': f'Internal server error: {str(e)}'}), 500


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
        logger.exception("Health check failed")
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


def save_user_request(query, emojis, limit, analysis):
    conn = get_connection()
    try:
        emojis_payload = psycopg2.extras.Json(emojis) if emojis else None
        analysis_payload = psycopg2.extras.Json(analysis) if analysis else None
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_requests (
                        text_description,
                        emojis,
                        num_songs_requested,
                        gemini_analysis
                    )
                    VALUES (%s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (
                        query,
                        emojis_payload,
                        limit,
                        analysis_payload
                    )
                )
                row = cur.fetchone()
                request_id = row['id'] if row else None
                return request_id
    except Exception:
        logger.exception("Failed to save user request to the database")
        raise
    finally:
        conn.close()


def save_recommended_song(request_id, position, song):
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO recommended_songs (
                        request_id,
                        position,
                        spotify_track_id,
                        title,
                        artist,
                        album,
                        album_art,
                        preview_url,
                        spotify_url,
                        release_year,
                        duration_ms,
                        duration_formatted,
                        why_gemini_chose,
                        matched_criteria
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        request_id,
                        position,
                        song.get("id"),
                        song.get("title"),
                        song.get("artist"),
                        song.get("album"),
                        song.get("album_art"),
                        song.get("preview_url"),
                        song.get("spotify_url"),
                        song.get("release_year"),
                        song.get("duration_ms"),
                        song.get("duration_formatted"),
                        song.get("why"),
                        psycopg2.extras.Json(song.get("matched_criteria")) 
                            if song.get("matched_criteria") else None
                    )
                )
    except Exception:
        logger.exception("Failed to save recommended song to the database")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    logger.info("Starting Text-to-Spotify API server...")
    app.run(debug=Config.DEBUG, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
