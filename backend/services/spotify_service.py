import logging
from typing import Dict, List, Optional

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from .base_music_service import BaseMusicService
from ._track_matching import (
    clean_title,
    format_duration,
    primary_artist,
    score_candidate,
)

logger = logging.getLogger(__name__)


class SpotifyService(BaseMusicService):
    """Music enrichment provider backed by the Spotify Web API."""

    def __init__(self, client_id: str, client_secret: str, config: Optional[Dict] = None):
        self.client_credentials_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret,
        )
        self.sp = spotipy.Spotify(client_credentials_manager=self.client_credentials_manager)
        self.config = config or {}

    def search_track(self, title: str, artist: str) -> Optional[Dict]:
        try:
            cleaned_title = clean_title(title)
            cleaned_artist = primary_artist(artist)

            queries = [
                f'track:"{cleaned_title}" artist:"{cleaned_artist}"',
                f'"{cleaned_title}" "{cleaned_artist}"',
                f'"{cleaned_title}"',
            ]

            best_match = self._find_best_match(queries, cleaned_title, cleaned_artist)

            threshold = self.config.get('matching', {}).get('threshold', 60)
            if not best_match or best_match[0] < threshold:
                logger.warning(
                    f"No strong match for: {title} by {artist} "
                    f"(best_score={best_match[0] if best_match else 'n/a'})"
                )
                return None

            track = best_match[1]
            track_data = self._build_track_payload(track)
            logger.info(f"Found track: {title} by {artist}")
            return track_data
        except Exception as e:
            logger.error(f"Error searching for track '{title}' by '{artist}': {e}")
            return None

    def enrich_songs(self, songs: List[Dict[str, str]], min_popularity: Optional[int] = None) -> List[Dict]:
        enriched_songs: List[Dict] = []

        for song in songs:
            try:
                track_data = self.search_track(song['title'], song['artist'])
                if track_data:
                    track_data.update({
                        'why': song.get('why'),
                        'matched_criteria': song.get('matched_criteria'),
                    })
                    if min_popularity is not None:
                        track_popularity = track_data.get('popularity', 0) or 0
                        if track_popularity < min_popularity:
                            logger.info(
                                f"Skipping {song['title']} by {song['artist']} "
                                f"(popularity: {track_popularity} < {min_popularity})"
                            )
                            continue
                    enriched_songs.append(track_data)
                else:
                    if min_popularity is not None and 0 < min_popularity:
                        logger.info(
                            f"Skipping {song['title']} by {song['artist']} "
                            f"(not found in Spotify, popularity: 0 < {min_popularity})"
                        )
                        continue
                    enriched_songs.append(self._fallback_payload(song))
            except Exception as e:
                logger.error(f"Error enriching song {song}: {e}")
                if min_popularity is not None and 0 < min_popularity:
                    continue
                enriched_songs.append(self._fallback_payload(song))

        logger.info(f"Enriched {len(enriched_songs)} songs with Spotify data")
        return enriched_songs

    def _find_best_match(self, queries: List[str], cleaned_title: str, cleaned_artist: str):
        best_match = None
        search_limit = self.config.get('search', {}).get('limit', 5)
        market = self.config.get('search', {}).get('market', 'US')
        early_exit_score = self.config.get('matching', {}).get('early_exit_score', 80)
        primary_bonus = self.config.get('matching', {}).get('primary_artist_bonus', 50)
        any_bonus = self.config.get('matching', {}).get('any_artist_bonus', 20)

        for query in queries:
            results = self.sp.search(q=query, type="track", limit=search_limit, market=market)
            for track in results.get("tracks", {}).get("items", []):
                track_artists = [a.get("name", "") for a in track.get("artists", [])]
                score = score_candidate(
                    cleaned_title,
                    cleaned_artist,
                    track.get("name", ""),
                    track_artists,
                    primary_artist_bonus=primary_bonus,
                    any_artist_bonus=any_bonus,
                )
                if not best_match or score > best_match[0]:
                    best_match = (score, track)
            if best_match and best_match[0] >= early_exit_score:
                break
        return best_match

    def _build_track_payload(self, track: Dict) -> Dict:
        album = track.get('album') or {}
        images = album.get('images') or []
        return {
            'track_id': track.get('id'),
            'title': track.get('name'),
            'artist': track.get('artists', [{}])[0].get('name') if track.get('artists') else None,
            'album': album.get('name'),
            'album_art': images[0].get('url') if images else None,
            'preview_url': track.get('preview_url'),
            'track_url': track.get('external_urls', {}).get('spotify') if track.get('external_urls') else None,
            'release_year': (album.get('release_date', '')[:4] if album.get('release_date') else None),
            'duration_ms': track.get('duration_ms'),
            'duration_formatted': format_duration(track.get('duration_ms')),
            'popularity': track.get('popularity', 0),
        }

    @staticmethod
    def _fallback_payload(song: Dict) -> Dict:
        return {
            'track_id': None,
            'title': song['title'],
            'artist': song['artist'],
            'album': 'Unknown Album',
            'album_art': None,
            'preview_url': None,
            'track_url': None,
            'release_year': None,
            'duration_ms': None,
            'duration_formatted': None,
            'why': song.get('why'),
            'matched_criteria': song.get('matched_criteria'),
            'popularity': 0,
        }

    def test_connection(self) -> bool:
        try:
            self.sp.search(q="test", type='track', limit=1)
            return True
        except Exception as e:
            logger.error(f"Spotify connection test failed: {e}")
            return False
