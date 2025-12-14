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


def parse_emojis(emojis_raw: Optional[List[str]], max_emojis: int = 12) -> List[str]:
    if emojis_raw is None:
        return []
    if not isinstance(emojis_raw, list):
        raise ValidationError("emojis must be an array of strings", 400)

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


def normalize_limit(raw_limit: Any, default: int = 10, min_limit: int = 10, max_limit: int = 50) -> int:
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


def compute_first_request_size(limit: int, popularity_label: Optional[str] = None, cap: int = 30) -> int:
    """Size first Gemini request; capped for consistency."""
    base = max(int(limit * 1.5), limit)
    return min(base, cap)


def compute_second_request_size(remaining_needed: int, cap: int = 40) -> int:
    """Size second Gemini request with a small floor and cap."""
    return min(max(int(remaining_needed * 2), 5), cap)
