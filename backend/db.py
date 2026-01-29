# backend/db.py
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from config import DATABASE_URL, Config
import logging
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level pool instance (initialized lazily)
_connection_pool: Optional[pool.ThreadedConnectionPool] = None
_pool_init_failed = False


def _initialize_pool():
    """
    Initialize the connection pool. Called lazily on first connection request.
    Returns True if successful, False otherwise.
    """
    global _connection_pool, _pool_init_failed

    if _connection_pool is not None:
        return True

    if _pool_init_failed:
        return False

    # Check if DATABASE_URL is configured
    if not DATABASE_URL:
        logger.warning("DATABASE_URL not configured. Database features disabled.")
        _pool_init_failed = True
        return False

    # Get pool configuration from JSON config
    min_conn = Config.get('database.connection_pool.min_connections', 2)
    max_conn = Config.get('database.connection_pool.max_connections', 10)

    try:
        _connection_pool = pool.ThreadedConnectionPool(
            minconn=min_conn,
            maxconn=max_conn,
            dsn=DATABASE_URL,
            cursor_factory=RealDictCursor
        )
        logger.info(f"Database connection pool initialized (min={min_conn}, max={max_conn})")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database connection pool: {e}")
        logger.warning("Database features will be unavailable")
        _pool_init_failed = True
        return False


def close_pool():
    """Close all connections in the pool. Called during app shutdown."""
    global _connection_pool

    if _connection_pool is not None:
        try:
            _connection_pool.closeall()
            logger.info("Database connection pool closed")
        except Exception as e:
            logger.error(f"Error closing connection pool: {e}")
        finally:
            _connection_pool = None


@contextmanager
def get_db_connection():
    """
    Context manager that yields a database connection from the pool.
    Automatically returns connection to pool on exit.

    Yields None if database is unavailable (graceful degradation).

    Usage:
        with get_db_connection() as conn:
            if conn is None:
                # Database unavailable, handle gracefully
                return
            with conn.cursor() as cur:
                cur.execute(query, params)
                conn.commit()
    """
    # Lazy initialization on first use
    if not _initialize_pool():
        # Pool initialization failed, yield None for graceful degradation
        yield None
        return

    conn = None
    try:
        # Get connection from pool (blocks if pool exhausted)
        conn = _connection_pool.getconn()
        yield conn
    except pool.PoolError as e:
        logger.error(f"Connection pool error: {e}")
        yield None
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        yield None
    finally:
        # Always return connection to pool
        if conn is not None:
            try:
                conn.rollback()  # Clear any uncommitted transaction
                _connection_pool.putconn(conn)
            except Exception as e:
                logger.error(f"Error returning connection to pool: {e}")


# Deprecated: Keep for backward compatibility during migration
def get_connection():
    """
    DEPRECATED: Use get_db_connection() context manager instead.
    This function is kept for backward compatibility only.
    """
    logger.warning("get_connection() is deprecated. Use get_db_connection() context manager instead.")
    if not _initialize_pool():
        raise RuntimeError("Database connection pool not available")
    return _connection_pool.getconn()


def test_connection():
    """Test database connectivity using the connection pool."""
    with get_db_connection() as conn:
        if conn is None:
            print("DB test FAILED: Pool not available")
            return
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                row = cur.fetchone()
                print("DB test OK, result:", row)
        except Exception as e:
            print("DB test FAILED:", e)
