# backend/db.py
import psycopg2
from psycopg2.extras import RealDictCursor
from config import DATABASE_URL


def get_connection():
    """Return a new database connection."""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def test_connection():
    """Simple test: connect and run SELECT 1."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        row = cur.fetchone()
        cur.close()
        conn.close()
        print("DB test OK, result:", row)
    except Exception as e:
        print("DB test FAILED:", e)
