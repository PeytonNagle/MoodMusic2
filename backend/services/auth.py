"""JWT auth helpers: token issuance, decoding, and a route decorator."""

import logging
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Optional

import jwt
from flask import g, jsonify, request

from config import Config

logger = logging.getLogger(__name__)

_ALGORITHM = "HS256"
_TOKEN_TTL = timedelta(days=7)


def issue_token(user_id: int) -> str:
    """Issue a signed JWT for the given user_id."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + _TOKEN_TTL).timestamp()),
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm=_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Return decoded payload or None if invalid/expired."""
    try:
        return jwt.decode(token, Config.SECRET_KEY, algorithms=[_ALGORITHM])
    except jwt.PyJWTError as e:
        logger.info("JWT decode failed: %s", e)
        return None


def _extract_bearer_token() -> Optional[str]:
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    return header.split(" ", 1)[1].strip() or None


def require_auth(fn):
    """Decorator: require a valid Bearer JWT; sets `g.user_id` (int)."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = _extract_bearer_token()
        if not token:
            return jsonify({"success": False, "error": "Missing or invalid Authorization header"}), 401

        payload = decode_token(token)
        if not payload or "sub" not in payload:
            return jsonify({"success": False, "error": "Invalid or expired token"}), 401

        try:
            g.user_id = int(payload["sub"])
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Invalid token subject"}), 401

        return fn(*args, **kwargs)

    return wrapper
