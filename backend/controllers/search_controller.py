"""Search controller handling search, analyze, and recommend endpoints."""

import logging
from flask import request, jsonify
from config import Config
from services.requests_utils import (
    ValidationError,
    compute_first_request_size,
    compute_second_request_size,
    normalize_limit,
    parse_emojis,
    parse_query,
    parse_user_id,
    require_json_body,
    require_query_or_emojis,
)
from .base_controller import BaseController

logger = logging.getLogger(__name__)


class SearchController(BaseController):
    """Controller for search and recommendation endpoints."""

    def __init__(self, mood_service, spotify_service, save_queue=None):
        """
        Initialize search controller with services.

        Args:
            mood_service: AI mood service instance (BaseMoodService - could be GeminiService or OllamaService)
            spotify_service: SpotifyService instance
            save_queue: Optional queue for background saves
        """
        super().__init__()
        self.mood_service = mood_service
        self.spotify_service = spotify_service
        self.save_queue = save_queue

        # Popularity configuration
        self.popularity_ranges = Config.get('popularity.ranges', {
            "Any": None,
            "Global / Superstar": (90, 100),
            "Hot / Established": (75, 89),
            "Buzzing / Moderate": (50, 74),
            "Growing": (25, 49),
            "Rising": (15, 24),
            "Under the Radar": (0, 14),
        })
        self.popularity_tolerance = Config.get('popularity.base_tolerance', 5)
        self.popularity_extra_tolerance = Config.get('popularity.extra_tolerance', {
            "Growing": 10,
            "Rising": 12,
            "Under the Radar": 15,
        })

    def _require_services(self, needs_spotify: bool = False, **empty_fields):
        """Check required services are available.

        Returns a (jsonify_response, 500) tuple if a service is missing, else None.
        Pass empty_fields to match the calling endpoint's response shape, e.g.
        songs=[], analysis={}.
        """
        if not self.mood_service:
            provider = Config.get_ai_provider()
            return jsonify({
                'success': False,
                'error': f'AI service ({provider}) not configured. Please check your configuration.',
                **empty_fields
            }), 500
        if needs_spotify and not self.spotify_service:
            return jsonify({
                'success': False,
                'error': 'Spotify service not configured. Please add SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET to .env file.',
                **empty_fields
            }), 500
        return None

    def resolve_popularity_constraints(self, data):
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
            mapped = self.popularity_ranges.get(label_clean)
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
        extra_tol = self.popularity_extra_tolerance.get(label_clean, 0)
        min_pop = max(0, range_min - self.popularity_tolerance - extra_tol) if range_min is not None else None
        max_pop = min(100, range_max + self.popularity_tolerance + extra_tol) if range_max is not None else None

        return {
            "popularity_label": label_clean,
            "min_popularity": min_pop,
            "max_popularity": max_pop,
        }

    @staticmethod
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

    @staticmethod
    def add_unique_songs(target_list, songs, seen_keys):
        """Append only new songs to target_list using provided seen_keys set."""
        for song in songs or []:
            key = SearchController._song_identity(song)
            if key and key in seen_keys:
                continue
            if key:
                seen_keys.add(key)
            target_list.append(song)
        return target_list

    def filter_by_popularity(self, songs, min_popularity, max_popularity):
        """Filter songs list by popularity bounds if provided, deduping by id/title/artist."""
        return self.filter_by_popularity_with_seen(songs, min_popularity, max_popularity, seen_keys=None)

    def filter_by_popularity_with_seen(self, songs, min_popularity, max_popularity, seen_keys=None):
        """Filter songs list by popularity bounds if provided, deduping against seen_keys."""
        if seen_keys is None:
            seen_keys = set()
        if min_popularity is None and max_popularity is None:
            return self.add_unique_songs([], songs, seen_keys)
        filtered = []
        for song in songs:
            pop = song.get("popularity", 0) if isinstance(song, dict) else 0
            if min_popularity is not None and pop < min_popularity:
                continue
            if max_popularity is not None and pop > max_popularity:
                continue
            key = self._song_identity(song)
            if key and key in seen_keys:
                continue
            if key:
                seen_keys.add(key)
            filtered.append(song)
        return filtered

    def generate_recommendations(self, query, emojis, limit, analysis, popularity_label, min_popularity, max_popularity):
        """
        Shared recommendation flow for search and recommend endpoints.
        Attempts up to 2 AI provider calls with consistent sizing and popularity filtering.
        """
        provider = Config.get_ai_provider()
        enriched_songs = []
        enriched_seen = set()
        all_requested_songs = []
        max_attempts = Config.get('request_handling.max_recommendation_attempts', 2)

        def request_and_enrich(num_songs):
            num_to_request = max(1, int(num_songs))
            recommendations = self.mood_service.recommend_songs(
                query,
                analysis,
                num_to_request,
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
            enriched_batch = self.spotify_service.enrich_songs(new_songs, min_popularity=min_popularity)
            deduped_batch = []
            self.add_unique_songs(deduped_batch, enriched_batch, enriched_seen)
            return deduped_batch

        attempt = 0
        first_num_songs = compute_first_request_size(limit, popularity_label=popularity_label)
        attempt += 1
        logger.info(f"Attempt {attempt}: Requesting {first_num_songs} songs from {provider} (target {limit})...")
        enriched_songs.extend(request_and_enrich(first_num_songs))

        filtered_count = len(self.filter_by_popularity(enriched_songs, min_popularity, max_popularity))
        threshold_ratio = Config.get('popularity.minimum_filtered_threshold_ratio', 0.5)
        if attempt < max_attempts and filtered_count < max(1, int(limit * threshold_ratio)):
            remaining_needed = max(limit - filtered_count, 1)
            second_num_songs = compute_second_request_size(remaining_needed)
            attempt += 1
            logger.info(f"Attempt {attempt}: Requesting {second_num_songs} songs from {provider} (need ~{remaining_needed} more after filtering)...")
            enriched_songs.extend(request_and_enrich(second_num_songs))

        filtered = self.filter_by_popularity_with_seen(enriched_songs, min_popularity, max_popularity, set())
        filtered_seen = {k for k in (self._song_identity(s) for s in filtered) if k}
        attempts_exhausted = attempt >= max_attempts or len(filtered) < limit
        if attempts_exhausted and len(filtered) < limit and enriched_songs:
            logger.warning("Popularity filter removed some/all songs; padding with unfiltered results (final attempt).")
            padded = list(filtered)
            for s in enriched_songs:
                if len(padded) >= limit:
                    break
                self.add_unique_songs(padded, [s], filtered_seen)
            filtered = padded
        final_songs = filtered[:limit]

        if len(final_songs) < limit:
            logger.warning(f"Could only find {len(final_songs)} songs meeting popularity criteria (requested {limit})")

        logger.info(f"Final result: {len(final_songs)} songs")
        return final_songs

    def search_music(self):
        """
        Search for music based on text description.

        Expected JSON payload:
        {
            "query": "upbeat indie rock for a road trip",  # optional if emojis are provided
            "emojis": ["🙂", "🔥"],  # optional, up to 12
            "limit": 10  # optional, defaults to 10
        }

        Returns:
        {
            "success": true,
            "songs": [...],
            "analysis": {...},
            "error": null
        }
        """
        try:
            data = require_json_body(request)
            query = parse_query(data)
            popularity_ctx = self.resolve_popularity_constraints(data)
            popularity_label = popularity_ctx["popularity_label"]
            min_popularity = popularity_ctx["min_popularity"]
            max_popularity = popularity_ctx["max_popularity"]
            emojis = parse_emojis(data.get('emojis'))
            limit = normalize_limit(data.get('limit', 10))
            require_query_or_emojis(query, emojis)

            logger.info(
                f"Processing search query: '{query}' with limit: {limit}, popularity_label: {popularity_label}, "
                f"min_popularity: {min_popularity}, max_popularity: {max_popularity}, emojis: {emojis}"
            )

            err = self._require_services(needs_spotify=True, songs=[])
            if err:
                return err

            # Step 1: Fast mood/constraint analysis
            provider = Config.get_ai_provider()
            logger.info(f"Getting mood analysis from {provider}...")
            analysis_result = self.mood_service.analyze_mood(query, emojis)
            analysis = analysis_result.get('analysis', {}) if isinstance(analysis_result, dict) else {}

            enriched_songs = self.generate_recommendations(
                query,
                emojis,
                limit,
                analysis,
                popularity_label,
                min_popularity,
                max_popularity,
            )

            return jsonify({
                'success': True,
                'songs': enriched_songs,
                'analysis': analysis,
                'error': None
            })

        except ValidationError as ve:
            return jsonify({
                'success': False,
                'songs': [],
                'error': ve.message
            }), ve.status_code
        except Exception as e:
            logger.exception("Error processing search request")
            return jsonify({
                'success': False,
                'songs': [],
                'error': f'Internal server error: {str(e)}'
            }), 500

    def analyze(self):
        """Fast mood/constraint analysis endpoint."""
        try:
            data = require_json_body(request)
            query = parse_query(data)
            emojis = parse_emojis(data.get('emojis'))

            require_query_or_emojis(query, emojis)

            err = self._require_services(analysis={})
            if err:
                return err

            provider = Config.get_ai_provider()
            logger.info(f"Getting mood analysis from {provider} (analyze endpoint)...")
            analysis_result = self.mood_service.analyze_mood(query, emojis)
            analysis = analysis_result.get('analysis', {}) if isinstance(analysis_result, dict) else {}

            return jsonify({'success': True, 'analysis': analysis, 'error': None})

        except ValidationError as ve:
            return jsonify({'success': False, 'analysis': {}, 'error': ve.message}), ve.status_code
        except Exception as e:
            logger.exception("Error processing analyze request")
            return jsonify({'success': False, 'analysis': {}, 'error': f'Internal server error: {str(e)}'}), 500

    def recommend(self):
        """Recommend songs using provided analysis (or auto-analyze if missing)."""
        try:
            data = require_json_body(request)
            query = parse_query(data)
            limit = normalize_limit(data.get('limit', 10))
            popularity_ctx = self.resolve_popularity_constraints(data)
            popularity_label = popularity_ctx["popularity_label"]
            min_popularity = popularity_ctx["min_popularity"]
            max_popularity = popularity_ctx["max_popularity"]
            analysis_payload = data.get('analysis', {}) or {}
            user_id = parse_user_id(data.get('user_id'))
            emojis = parse_emojis(data.get('emojis'))

            require_query_or_emojis(query, emojis)

            err = self._require_services(needs_spotify=True, songs=[], analysis={})
            if err:
                return err

            analysis = analysis_payload if isinstance(analysis_payload, dict) else {}
            if not analysis:
                provider = Config.get_ai_provider()
                logger.info(f"No analysis provided; generating via {provider}...")
                analysis_result = self.mood_service.analyze_mood(query, emojis)
                analysis = analysis_result.get('analysis', {}) if isinstance(analysis_result, dict) else {}

            enriched_songs = self.generate_recommendations(
                query,
                emojis,
                limit,
                analysis,
                popularity_label,
                min_popularity,
                max_popularity,
            )

            # Queue async save if save_queue is available
            if self.save_queue and Config.get('database.save_queue.enabled', True):
                import queue
                job_data = {
                    "query": query,
                    "emojis": emojis,
                    "limit": limit,
                    "analysis": analysis,
                    "songs": enriched_songs,
                    "user_id": user_id,
                }

                behavior = Config.get('database.save_queue.behavior_on_full', 'skip')
                try:
                    if behavior == 'skip':
                        self.save_queue.put_nowait(job_data)
                    elif behavior == 'block':
                        self.save_queue.put(job_data, block=True, timeout=5)
                    else:  # 'error'
                        self.save_queue.put_nowait(job_data)
                except queue.Full:
                    if behavior == 'error':
                        logger.error("Save queue is full; cannot save request")
                    else:
                        logger.warning("Save queue is full; skipping async DB save for this request.")

            return jsonify({'success': True, 'songs': enriched_songs, 'analysis': analysis, 'error': None})

        except ValidationError as ve:
            return jsonify({'success': False, 'songs': [], 'analysis': {}, 'error': ve.message}), ve.status_code
        except Exception as e:
            logger.exception("Error processing recommend request")
            return jsonify({'success': False, 'songs': [], 'analysis': {}, 'error': f'Internal server error: {str(e)}'}), 500
