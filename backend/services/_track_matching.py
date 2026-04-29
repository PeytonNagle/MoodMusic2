"""Provider-agnostic helpers for cleaning track metadata and scoring fuzzy matches."""

import re
from difflib import SequenceMatcher
from typing import Optional


def clean_title(text: str) -> str:
    """Normalize song titles by removing feature/suffix noise for better matching."""
    text = text or ""
    lowered = text.lower()
    lowered = re.sub(r"\s*[\(\[].*?[\)\]]", "", lowered)
    lowered = re.sub(r"\s*-\s*(remaster(ed)?(?: \d{4})?|live.*|single mix|radio edit).*", "", lowered)
    lowered = re.sub(r"\s*(feat\.?|ft\.?|featuring|with)\s+.*", "", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def primary_artist(artist: str) -> str:
    """Extract primary artist, ignoring featured collaborators."""
    artist = artist or ""
    parts = re.split(
        r"\s*(,|&|/| x | ft\.?| feat\.?| featuring )\s*",
        artist,
        maxsplit=1,
        flags=re.IGNORECASE,
    )
    return parts[0].strip()


def title_similarity(a: str, b: str) -> float:
    """Return a 0-100 similarity score between two cleaned titles."""
    return SequenceMatcher(None, a or "", b or "").ratio() * 100


def score_candidate(
    cleaned_title: str,
    cleaned_primary_artist: str,
    candidate_title: str,
    candidate_artists: list,
    primary_artist_bonus: int = 50,
    any_artist_bonus: int = 20,
) -> float:
    """Score a candidate track based on title similarity and artist match."""
    cleaned_candidate_title = clean_title(candidate_title)
    lowered_artists = [(a or "").lower() for a in candidate_artists]

    score = title_similarity(cleaned_title, cleaned_candidate_title)

    if lowered_artists:
        primary_lower = cleaned_primary_artist.lower()
        if primary_lower == lowered_artists[0]:
            score += primary_artist_bonus
        if primary_lower in lowered_artists:
            score += any_artist_bonus

    return score


def format_duration(duration_ms: Optional[int]) -> Optional[str]:
    """Convert milliseconds to MM:SS, or None when no duration is available."""
    if not duration_ms:
        return None

    seconds = duration_ms // 1000
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes}:{seconds:02d}"
