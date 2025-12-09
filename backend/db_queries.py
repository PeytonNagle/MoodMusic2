# backend/db_queries.py

from db import get_connection
import json

def save_user_request(
    text_description,
    emojis,
    num_songs,
    analysis,
    user_id=None
):
    """
    Insert ONE new row into user_requests.
    Returns the new request_id.
    """
    query = """
        INSERT INTO user_requests
            (user_id, text_description, emojis, num_songs_requested, gemini_analysis)
        VALUES
            (%s, %s, %s, %s, %s)
        RETURNING id;
    """

    # Convert Python dict/list to JSON if needed
    emojis_json = json.dumps(emojis) if emojis else None
    analysis_json = json.dumps(analysis) if analysis else None

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (user_id, text_description, emojis_json, num_songs, analysis_json)
            )
            new_id = cur.fetchone()["id"]
            conn.commit()
            return new_id