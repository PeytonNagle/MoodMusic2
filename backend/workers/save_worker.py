"""Background worker for saving requests and songs to database."""

import logging
import threading
import queue
from typing import Optional
from config import Config
from db import db_connection
import psycopg2.extras

logger = logging.getLogger(__name__)


class SaveWorker:
    """Background worker to persist requests/songs without blocking responses."""

    def __init__(self, maxsize: Optional[int] = None):
        """
        Initialize save worker.

        Args:
            maxsize: Maximum queue size. If None, uses config value.
        """
        if maxsize is None:
            maxsize = Config.save_queue_max_size()

        self.queue: "queue.Queue[dict]" = queue.Queue(maxsize=maxsize)
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            name="save-worker",
            daemon=True
        )
        self.running = False

    def start(self):
        """Start the background worker thread."""
        if not self.running:
            self.running = True
            self.worker_thread.start()
            logger.info("Save worker started")

    def stop(self):
        """Stop the background worker thread gracefully."""
        if self.running:
            self.queue.put(None)  # Signal to stop
            self.worker_thread.join(timeout=5)
            self.running = False
            logger.info("Save worker stopped")

    def _worker_loop(self):
        """Main worker loop that processes save jobs from queue."""
        while True:
            job = self.queue.get()
            if job is None:
                self.queue.task_done()
                break
            try:
                request_id = None
                # Only save requests if enabled in config
                if Config.save_requests_enabled():
                    request_id = self._save_user_request(
                        job["query"],
                        job.get("emojis"),
                        job["limit"],
                        job["analysis"],
                        job.get("user_id"),
                    )

                # Only save songs if enabled and we have a request_id
                if Config.save_songs_enabled() and request_id:
                    for i, song in enumerate(job["songs"]):
                        self._save_recommended_song(request_id, i + 1, song, job.get("user_id"))

                if request_id:
                    logger.info(f"Background save complete (request_id={request_id}, songs={len(job['songs'])})")
            except Exception:
                logger.exception("Background save failed")
            finally:
                self.queue.task_done()

    @staticmethod
    def _save_user_request(query, emojis, limit, analysis, user_id=None):
        """Save user request to database."""
        with db_connection("save user request") as conn:
            if conn is None:
                return None

            try:
                emojis_payload = psycopg2.extras.Json(emojis) if emojis else None
                analysis_payload = psycopg2.extras.Json(analysis) if analysis else None
                with conn:  # Transaction context
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

    @staticmethod
    def _save_recommended_song(request_id, position, song, user_id=None):
        """Save recommended song to database."""
        with db_connection("save recommended song") as conn:
            if conn is None:
                return

            try:
                with conn:  # Transaction context
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
