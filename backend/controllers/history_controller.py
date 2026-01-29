"""History controller handling user history endpoints."""

import logging
from flask import request, jsonify
from config import Config
from db import get_db_connection
from .base_controller import BaseController

logger = logging.getLogger(__name__)


class HistoryController(BaseController):
    """Controller for user history endpoints."""

    def __init__(self):
        """Initialize history controller."""
        super().__init__()

    def fetch_user_history_records(self, user_id: int, limit: int = 20):
        """Fetch user history records from database."""
        with get_db_connection() as conn:
            if conn is None:
                logger.warning("Database unavailable, returning empty history")
                return []

            try:
                with conn:  # Transaction context
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

    def get_user_history(self, user_id):
        """Get user history endpoint."""
        if user_id <= 0:
            return jsonify({"success": False, "history": [], "error": "Invalid user id"}), 400

        limit_param = request.args.get("limit", Config.get('database.history.default_limit', 20))
        try:
            limit = int(limit_param)
        except (ValueError, TypeError):
            limit = Config.get('database.history.default_limit', 20)
        limit = max(1, min(limit, Config.get('database.history.max_limit', 50)))

        try:
            history_records = self.fetch_user_history_records(user_id, limit)
            return jsonify({"success": True, "history": history_records})
        except Exception:
            return jsonify({"success": False, "history": [], "error": "Failed to load history"}), 500
