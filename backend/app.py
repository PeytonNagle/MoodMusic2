
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import os
import threading
import queue
from config import Config
from services.gemini_service import GeminiService
from db import get_connection
from services.spotify_service import SpotifyService
import psycopg2.extras
import json
from werkzeug.security import generate_password_hash, check_password_hash
from psycopg2 import errors
from db_queries import create_user, get_user_by_email




# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Background queue for async DB saves
SAVE_QUEUE: "queue.Queue[dict]" = queue.Queue(maxsize=100)


def _save_worker():
    """Background worker to persist requests/songs without blocking responses."""
    while True:
        job = SAVE_QUEUE.get()
        if job is None:
            SAVE_QUEUE.task_done()
            break
        try:
            request_id = save_user_request(
                job["query"],
                job.get("emojis"),
                job["limit"],
                job["analysis"],
                job.get("user_id"),
            )
            for i, song in enumerate(job["songs"]):
                save_recommended_song(request_id, i + 1, song, job.get("user_id"))
            logger.info(f"Background save complete (request_id={request_id}, songs={len(job['songs'])})")
        except Exception:
            logger.exception("Background save failed")
        finally:
            SAVE_QUEUE.task_done()


SAVE_WORKER = threading.Thread(target=_save_worker, name="save-worker", daemon=True)
SAVE_WORKER.start()

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
POPULARITY_EXTRA_TOLERANCE = {
    "Growing": 10,
    "Rising": 12,
    "Under the Radar": 15,
}


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
        if label_clean.lower() == "any":
            label_clean = "Any"
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
    extra_tol = POPULARITY_EXTRA_TOLERANCE.get(label_clean, 0)
    min_pop = max(0, range_min - POPULARITY_TOLERANCE - extra_tol) if range_min is not None else None
    max_pop = min(100, range_max + POPULARITY_TOLERANCE + extra_tol) if range_max is not None else None

    return {
        "popularity_label": label_clean,
        "min_popularity": min_pop,
        "max_popularity": max_pop,
    }


def filter_by_popularity(songs, min_popularity, max_popularity):
    """Filter songs list by popularity bounds if provided, deduping by id/title/artist."""
    return filter_by_popularity_with_seen(songs, min_popularity, max_popularity, seen_keys=None)


def _song_identity(song):
    """Build a stable key for a song using id when present, else title|artist."""
    if not isinstance(song, dict):
        return None
    song_id = song.get("id")
    if song_id:
        return f"id:{str(song_id).strip().lower()}"
    title = str(song.get("title", "") or "").strip().lower()
    artist = str(song.get("artist", "") or "").strip().lower()
    if title or artist:
        return f"{title}|{artist}"
    return None


def add_unique_songs(target_list, songs, seen_keys):
    """Append only new songs to target_list using provided seen_keys set."""
    for song in songs or []:
        key = _song_identity(song)
        if key and key in seen_keys:
            continue
        if key:
            seen_keys.add(key)
        target_list.append(song)
    return target_list


def filter_by_popularity_with_seen(songs, min_popularity, max_popularity, seen_keys=None):
    """Filter songs list by popularity bounds if provided, deduping against seen_keys."""
    if seen_keys is None:
        seen_keys = set()
    if min_popularity is None and max_popularity is None:
        return add_unique_songs([], songs, seen_keys)
    filtered = []
    for song in songs:
        pop = song.get("popularity", 0) if isinstance(song, dict) else 0
        if min_popularity is not None and pop < min_popularity:
            continue
        if max_popularity is not None and pop > max_popularity:
            continue
        key = _song_identity(song)
        if key and key in seen_keys:
            continue
        if key:
            seen_keys.add(key)
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

        # Step 2: Get song recommendations using the analysis (fast: max 2 Gemini calls)
        enriched_songs = []
        enriched_seen = set()
        all_requested_songs = []  # Track all songs we've requested to avoid duplicates
        max_attempts = 2

        def request_and_enrich(num_songs):
            recommendations = gemini_service.recommend_songs(
                query,
                analysis,
                num_songs,
                emojis,
                min_popularity=min_popularity,
                popularity_label=popularity_label,
            )
            songs_from_ai = recommendations.get('songs', []) if isinstance(recommendations, dict) else recommendations
            if not songs_from_ai:
                return []

            new_songs = []
            for song in songs_from_ai:
                song_key = f"{song.get('title', '').lower()}|{song.get('artist', '').lower()}"
                if song_key not in all_requested_songs:
                    new_songs.append(song)
                    all_requested_songs.append(song_key)
            
            if not new_songs:
                return []

            logger.info(f"Enriching {len(new_songs)} new songs with Spotify data...")
            enriched_batch = spotify_service.enrich_songs(new_songs, min_popularity=min_popularity)
            deduped_batch = []
            add_unique_songs(deduped_batch, enriched_batch, enriched_seen)
            return deduped_batch

        attempt = 0
        first_num_songs = min(limit * 1.5, 30)
        attempt += 1
        logger.info(f"Attempt {attempt}: Requesting {first_num_songs} songs from Gemini (target {limit})...")
        enriched_songs.extend(request_and_enrich(first_num_songs))

        filtered_count = len(filter_by_popularity(enriched_songs, min_popularity, max_popularity))
        if attempt < max_attempts and filtered_count < max(1, limit // 2):
            remaining_needed = limit - filtered_count
            second_num_songs = min(max(remaining_needed * 2, 5), 50)
            attempt += 1
            logger.info(f"Attempt {attempt}: Requesting {second_num_songs} songs from Gemini (need ~{remaining_needed} more after filtering)...")
            enriched_songs.extend(request_and_enrich(second_num_songs))

        filtered = filter_by_popularity_with_seen(enriched_songs, min_popularity, max_popularity, set())
        filtered_seen = {k for k in (_song_identity(s) for s in filtered) if k}
        attempts_exhausted = attempt >= max_attempts or len(filtered) < limit
        if attempts_exhausted and len(filtered) < limit and enriched_songs:
            logger.warning("Popularity filter removed some/all songs; padding with unfiltered results (final attempt).")
            padded = list(filtered)
            for s in enriched_songs:
                if len(padded) >= limit:
                    break
                add_unique_songs(padded, [s], filtered_seen)
            filtered = padded
        enriched_songs = filtered[:limit]
        
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
        user_id_raw = data.get('user_id')
        try:
            user_id = int(user_id_raw)
        except (ValueError, TypeError):
            user_id = None
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

        # Keep requesting until we have enough songs that meet popularity criteria (fast: max 2 Gemini calls)
        enriched_songs = []
        enriched_seen = set()
        all_requested_songs = []  # Track all songs we've requested to avoid duplicates
        max_attempts = 2

        def request_and_enrich(num_songs):
            recommendations = gemini_service.recommend_songs(
                query,
                analysis,
                num_songs,
                emojis,
                min_popularity=min_popularity,
                popularity_label=popularity_label,
            )
            songs_from_ai = recommendations.get('songs', []) if isinstance(recommendations, dict) else recommendations
            if not songs_from_ai:
                return []

            new_songs = []
            for song in songs_from_ai:
                song_key = f"{song.get('title', '').lower()}|{song.get('artist', '').lower()}"
                if song_key not in all_requested_songs:
                    new_songs.append(song)
                    all_requested_songs.append(song_key)
            
            if not new_songs:
                return []

            logger.info(f"Enriching {len(new_songs)} new songs with Spotify data...")
            enriched_batch = spotify_service.enrich_songs(new_songs, min_popularity=min_popularity)
            deduped_batch = []
            add_unique_songs(deduped_batch, enriched_batch, enriched_seen)
            return deduped_batch

        attempt = 0
        # Request sizing: smaller for high-popularity tiers, larger for low-popularity tiers
        if popularity_label in ("Global / Superstar", "Hot / Established"):
            first_num_songs = min(int(limit * 1.3), 50)
        elif popularity_label in ("Growing", "Rising", "Under the Radar"):
            first_num_songs = min(limit * 2, 50)
        elif popularity_label == "Any":
            first_num_songs = limit
        else:
            first_num_songs = min(limit * 1.6, 50)
        attempt += 1
        logger.info(f"Attempt {attempt}: Requesting {first_num_songs} songs from Gemini (target {limit})...")
        enriched_songs.extend(request_and_enrich(first_num_songs))

        filtered_count = len(filter_by_popularity(enriched_songs, min_popularity, max_popularity))
        if attempt < max_attempts and filtered_count < max(1, limit // 2):
            remaining_needed = limit - filtered_count
            second_num_songs = min(remaining_needed * 2, 50)
            attempt += 1
            logger.info(f"Attempt {attempt}: Requesting {second_num_songs} songs from Gemini (need ~{remaining_needed} more after filtering)...")
            enriched_songs.extend(request_and_enrich(second_num_songs))

        filtered = filter_by_popularity_with_seen(enriched_songs, min_popularity, max_popularity, set())
        filtered_seen = {k for k in (_song_identity(s) for s in filtered) if k}
        attempts_exhausted = attempt >= max_attempts or len(filtered) < limit
        if attempts_exhausted and len(filtered) < limit and enriched_songs:
            logger.warning("Popularity filter removed some/all songs; padding with unfiltered results (final attempt).")
            padded = list(filtered)
            for s in enriched_songs:
                if len(padded) >= limit:
                    break
                add_unique_songs(padded, [s], filtered_seen)
            filtered = padded[:limit]
        enriched_songs = filtered[:limit]
        
        if len(enriched_songs) < limit:
            logger.warning(f"Could only find {len(enriched_songs)} songs meeting popularity criteria (requested {limit})")

        # --- ASYNC SAVE REQUEST + SONGS TO DATABASE ---
        try:
            SAVE_QUEUE.put_nowait({
                "query": query,
                "emojis": emojis,
                "limit": limit,
                "analysis": analysis,
                "songs": enriched_songs,
                "user_id": user_id,
            })
        except queue.Full:
            logger.warning("Save queue is full; skipping async DB save for this request.")

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


@app.route('/api/users/register', methods=['POST'])
def register_user():
    """Register a new user with email + password hash."""
    try:
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Request must be JSON'}), 400

        data = request.get_json() or {}
        email = str(data.get('email', '') or '').strip().lower()
        password = data.get('password', '')
        display_name = str(data.get('display_name', '') or '').strip() or None

        if not email or not password:
            return jsonify({'success': False, 'error': 'Email and password are required'}), 400

        password_hash = generate_password_hash(password)
        try:
            user = create_user(email, password_hash, display_name)
        except errors.UniqueViolation:
            return jsonify({'success': False, 'error': 'Email already registered'}), 409

        public_user = {
            'id': user['id'],
            'email': user['email'],
            'display_name': user.get('display_name'),
            'created_at': user.get('created_at')
        }
        return jsonify({'success': True, 'user': public_user}), 201

    except Exception:
        logger.exception("Error registering user")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@app.route('/api/users/login', methods=['POST'])
def login_user():
    """Simple email/password login check."""
    try:
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Request must be JSON'}), 400

        data = request.get_json() or {}
        email = str(data.get('email', '') or '').strip().lower()
        password = data.get('password', '')

        if not email or not password:
            return jsonify({'success': False, 'error': 'Email and password are required'}), 400

        user = get_user_by_email(email)
        if not user or not check_password_hash(user['password_hash'], password):
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401

        public_user = {
            'id': user['id'],
            'email': user['email'],
            'display_name': user.get('display_name'),
            'created_at': user.get('created_at')
        }
        return jsonify({'success': True, 'user': public_user}), 200

    except Exception:
        logger.exception("Error logging in user")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


def fetch_user_history_records(user_id: int, limit: int = 20):
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        text_description,
                        emojis,
                        num_songs_requested,
                        gemini_analysis,
                        created_at
                    FROM user_requests
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s;
                    """,
                    (user_id, limit),
                )
                request_rows = cur.fetchall() or []
                request_ids = [row["id"] for row in request_rows]
                songs_by_request = {rid: [] for rid in request_ids}

                if request_ids:
                    cur.execute(
                        """
                        SELECT
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
                        FROM recommended_songs
                        WHERE request_id = ANY(%s)
                        ORDER BY request_id DESC, position ASC;
                        """,
                        (request_ids,),
                    )
                    song_rows = cur.fetchall() or []
                    for song in song_rows:
                        songs_by_request.setdefault(song["request_id"], []).append(
                            {
                                "position": song.get("position"),
                                "spotify_track_id": song.get("spotify_track_id"),
                                "title": song.get("title"),
                                "artist": song.get("artist"),
                                "album": song.get("album"),
                                "album_art": song.get("album_art"),
                                "preview_url": song.get("preview_url"),
                                "spotify_url": song.get("spotify_url"),
                                "release_year": song.get("release_year"),
                                "duration_ms": song.get("duration_ms"),
                                "duration_formatted": song.get("duration_formatted"),
                                "why_gemini_chose": song.get("why_gemini_chose"),
                                "matched_criteria": song.get("matched_criteria"),
                            }
                        )

                history_payload = []
                for row in request_rows:
                    request_id = row["id"]
                    history_payload.append(
                        {
                            "request_id": request_id,
                            "text_description": row.get("text_description"),
                            "emojis": row.get("emojis") or [],
                            "num_songs_requested": row.get("num_songs_requested"),
                            "analysis": row.get("gemini_analysis") or {},
                            "popularity_label": None,
                            "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
                            "songs": songs_by_request.get(request_id, []),
                        }
                    )
                return history_payload
    except Exception:
        logger.exception("Failed to fetch history from database")
        raise
    finally:
        conn.close()


@app.route('/api/history/<int:user_id>', methods=['GET'])
def get_user_history(user_id):
    if user_id <= 0:
        return jsonify({"success": False, "history": [], "error": "Invalid user id"}), 400
    limit_param = request.args.get("limit", 20)
    try:
        limit = int(limit_param)
    except (ValueError, TypeError):
        limit = 20
    limit = max(1, min(limit, 50))

    try:
        history_records = fetch_user_history_records(user_id, limit)
        return jsonify({"success": True, "history": history_records})
    except Exception:
        return jsonify({"success": False, "history": [], "error": "Failed to load history"}), 500


def save_user_request(query, emojis, limit, analysis, user_id=None):
    conn = get_connection()
    try:
        emojis_payload = psycopg2.extras.Json(emojis) if emojis else None
        analysis_payload = psycopg2.extras.Json(analysis) if analysis else None
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_requests (
                        user_id,
                        text_description,
                        emojis,
                        num_songs_requested,
                        gemini_analysis
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (
                        user_id,
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


def save_recommended_song(request_id, position, song, user_id=None):
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO recommended_songs (
                        request_id,
                        user_id,
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
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        request_id,
                        user_id,
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
