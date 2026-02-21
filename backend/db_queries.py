# backend/db_queries.py

from db import db_connection
import psycopg2.extras
import logging

logger = logging.getLogger(__name__)


def save_user_request(
    text_description,
    emojis,
    num_songs,
    analysis,
    user_id=None
):
    """
    Insert ONE new row into user_requests.
    Returns the new request_id, or None if database unavailable.
    """
    query = """
        INSERT INTO user_requests
            (user_id, text_description, emojis, num_songs_requested, gemini_analysis)
        VALUES
            (%s, %s, %s, %s, %s)
        RETURNING id;
    """

    emojis_payload = psycopg2.extras.Json(emojis) if emojis else None
    analysis_payload = psycopg2.extras.Json(analysis) if analysis else None

    with db_connection("save user request") as conn:
        if conn is None:
            return None

        with conn.cursor() as cur:
            cur.execute(
                query,
                (user_id, text_description, emojis_payload, num_songs, analysis_payload)
            )
            new_id = cur.fetchone()["id"]
            conn.commit()
            return new_id


def create_user(email, password_hash, display_name=None):
    """
    Create a new user account.
    Returns the inserted row (dict) on success, or None if database unavailable.
    """
    query = """
        INSERT INTO users (email, password_hash, display_name)
        VALUES (%s, %s, %s)
        RETURNING id, email, display_name, created_at;
    """
    with db_connection("create user") as conn:
        if conn is None:
            return None

        with conn.cursor() as cur:
            cur.execute(query, (email, password_hash, display_name))
            user = cur.fetchone()
            conn.commit()
            return user


def get_user_by_email(email):
    """Return user row (dict) by email, or None if not found or database unavailable."""
    query = """
        SELECT id, email, password_hash, display_name, created_at
        FROM users
        WHERE email = %s;
    """
    with db_connection("get user by email") as conn:
        if conn is None:
            return None

        with conn.cursor() as cur:
            cur.execute(query, (email,))
            return cur.fetchone()
