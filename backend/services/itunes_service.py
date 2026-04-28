"""iTunes Search API music enrichment service.

Uses the public iTunes Search API (no auth required) to enrich AI-generated
song titles with track metadata, album artwork, 30-second previews, and a
deep link to Apple Music.
"""

import logging
from typing import Dict, List, Optional

import requests

from .base_music_service import BaseMusicService
from ._track_matching import (
    clean_title,
    format_duration,
    primary_artist,
    score_candidate,
)

logger = logging.getLogger(__name__)

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"


class ItunesService(BaseMusicService):
    """Enrichment provider backed by the iTunes Search API."""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.country = self.config.get("country", "US")
        self.search_limit = self.config.get("search_limit", 5)
        self.timeout = self.config.get("timeout", 8)
        self.threshold = self.config.get("matching", {}).get("threshold", 60)
        self.early_exit_score = self.config.get("matching", {}).get("early_exit_score", 80)
        self.primary_artist_bonus = self.config.get("matching", {}).get("primary_artist_bonus", 50)
        self.any_artist_bonus = self.config.get("matching", {}).get("any_artist_bonus", 20)
        self.artwork_size = self.config.get("artwork_size", 600)

    def search_track(self, title: str, artist: str) -> Optional[Dict]:
        try:
            cleaned_title = clean_title(title)
            cleaned_artist = primary_artist(artist)

            terms = [
                f"{cleaned_title} {cleaned_artist}".strip(),
                cleaned_title,
            ]

            best = None  # (score, result)
            for term in terms:
                if not term:
                    continue
                results = self._query(term)
                for item in results:
                    score = score_candidate(
                        cleaned_title,
                        cleaned_artist,
                        item.get("trackName", ""),
                        [item.get("artistName", "")],
                        primary_artist_bonus=self.primary_artist_bonus,
                        any_artist_bonus=self.any_artist_bonus,
                    )
                    if best is None or score > best[0]:
                        best = (score, item)
                if best and best[0] >= self.early_exit_score:
                    break

            if not best or best[0] < self.threshold:
                logger.warning(
                    f"No strong iTunes match for: {title} by {artist} "
                    f"(best_score={best[0] if best else 'n/a'})"
                )
                return None

            payload = self._build_track_payload(best[1])
            logger.info(f"Found iTunes track: {title} by {artist}")
            return payload
        except Exception as e:
            logger.error(f"Error searching iTunes for '{title}' by '{artist}': {e}")
            return None

    def enrich_songs(
        self,
        songs: List[Dict[str, str]],
        min_popularity: Optional[int] = None,
    ) -> List[Dict]:
        """Enrich AI song suggestions with iTunes metadata.

        iTunes does not expose a popularity score, so popularity is always None
        and the min_popularity filter is intentionally ignored at this layer.
        """
        enriched: List[Dict] = []

        for song in songs:
            try:
                track_data = self.search_track(song["title"], song["artist"])
                if track_data:
                    track_data.update({
                        "why": song.get("why"),
                        "matched_criteria": song.get("matched_criteria"),
                    })
                    enriched.append(track_data)
                else:
                    enriched.append(self._fallback_payload(song))
            except Exception as e:
                logger.error(f"Error enriching song {song} via iTunes: {e}")
                enriched.append(self._fallback_payload(song))

        logger.info(f"Enriched {len(enriched)} songs with iTunes data")
        return enriched

    def test_connection(self) -> bool:
        try:
            resp = requests.get(
                ITUNES_SEARCH_URL,
                params={"term": "test", "media": "music", "entity": "song", "limit": 1},
                timeout=self.timeout,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"iTunes connection test failed: {e}")
            return False

    def _query(self, term: str) -> List[Dict]:
        params = {
            "term": term,
            "media": "music",
            "entity": "song",
            "limit": self.search_limit,
            "country": self.country,
        }
        resp = requests.get(ITUNES_SEARCH_URL, params=params, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", []) or []

    def _upscale_artwork(self, url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        size = f"{self.artwork_size}x{self.artwork_size}"
        return url.replace("100x100bb", f"{size}bb")

    def _build_track_payload(self, item: Dict) -> Dict:
        track_id = item.get("trackId")
        release_date = item.get("releaseDate") or ""
        return {
            "track_id": str(track_id) if track_id is not None else None,
            "title": item.get("trackName"),
            "artist": item.get("artistName"),
            "album": item.get("collectionName"),
            "album_art": self._upscale_artwork(item.get("artworkUrl100")),
            "preview_url": item.get("previewUrl"),
            "track_url": item.get("trackViewUrl"),
            "release_year": release_date[:4] if release_date else None,
            "duration_ms": item.get("trackTimeMillis"),
            "duration_formatted": format_duration(item.get("trackTimeMillis")),
            "popularity": None,
        }

    @staticmethod
    def _fallback_payload(song: Dict) -> Dict:
        return {
            "track_id": None,
            "title": song.get("title"),
            "artist": song.get("artist"),
            "album": "Unknown Album",
            "album_art": None,
            "preview_url": None,
            "track_url": None,
            "release_year": None,
            "duration_ms": None,
            "duration_formatted": None,
            "why": song.get("why"),
            "matched_criteria": song.get("matched_criteria"),
            "popularity": None,
        }
