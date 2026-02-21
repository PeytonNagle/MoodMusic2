from typing import Any, Dict, List, Optional


class ValidationError(Exception):
    """Represents a client-facing validation error."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def require_json_body(req) -> Dict[str, Any]:
    """Ensure the request has JSON and return the parsed body."""
    if not req.is_json:
        raise ValidationError("Request must be JSON", 400)
    data = req.get_json()
    if not data:
        raise ValidationError("Request body is missing", 400)
    return data


def parse_query(data: Dict[str, Any]) -> str:
    return str(data.get("query", "") or "").strip()


def parse_emojis(emojis_raw: Optional[List[str]], max_emojis: Optional[int] = None) -> List[str]:
    if emojis_raw is None:
        return []
    if not isinstance(emojis_raw, list):
        raise ValidationError("emojis must be an array of strings", 400)

    # Import Config lazily to avoid circular imports
    if max_emojis is None:
        from config import Config
        max_emojis = Config.get('request_handling.max_emojis', 12)

    emojis: List[str] = []
    seen = set()
    for emoji in emojis_raw:
        if not isinstance(emoji, str):
            raise ValidationError("emojis must be strings", 400)
        trimmed = emoji.strip()
        if trimmed and trimmed not in seen:
            emojis.append(trimmed)
            seen.add(trimmed)
        if len(emojis) >= max_emojis:
            break
    return emojis


def normalize_limit(raw_limit: Any, default: Optional[int] = None, min_limit: Optional[int] = None, max_limit: Optional[int] = None) -> int:
    # Import Config lazily to avoid circular imports
    from config import Config
    if default is None:
        default = Config.get('request_handling.song_limits.default', 10)
    if min_limit is None:
        min_limit = Config.get('request_handling.song_limits.min', 10)
    if max_limit is None:
        max_limit = Config.get('request_handling.song_limits.max', 50)

    try:
        value = int(raw_limit)
    except (ValueError, TypeError):
        return default
    if value < min_limit or value > max_limit:
        return default
    return value


def parse_user_id(user_id_raw: Any) -> Optional[int]:
    try:
        return int(user_id_raw)
    except (ValueError, TypeError):
        return None


def require_query_or_emojis(query: str, emojis: List[str]) -> None:
    if not query and not emojis:
        raise ValidationError("Please provide a search query or select emojis", 400)


def compute_first_request_size(limit: int, popularity_label: Optional[str] = None, cap: Optional[int] = None) -> int:
    """Size first Gemini request; capped for consistency."""
    # Import Config lazily to avoid circular imports
    from config import Config
    if cap is None:
        cap = Config.get('request_handling.sizing.first_request.cap', 30)
    multiplier = Config.get('request_handling.sizing.first_request.multiplier', 1.5)

    base = max(int(limit * multiplier), limit)
    return min(base, cap)


def compute_second_request_size(remaining_needed: int, cap: Optional[int] = None) -> int:
    """Size second Gemini request with a small floor and cap."""
    # Import Config lazily to avoid circular imports
    from config import Config
    if cap is None:
        cap = Config.get('request_handling.sizing.second_request.cap', 40)
    floor = Config.get('request_handling.sizing.second_request.floor', 5)
    multiplier = Config.get('request_handling.sizing.second_request.multiplier', 2.0)

    return min(max(int(remaining_needed * multiplier), floor), cap)
