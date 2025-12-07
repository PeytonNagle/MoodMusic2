import logging
import re
from difflib import SequenceMatcher
from typing import List, Dict, Optional

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

logger = logging.getLogger(__name__)

class SpotifyService:
    """Service for interacting with Spotify API using Spotipy"""
    
    def __init__(self, client_id: str, client_secret: str):
        """Initialize Spotify client with credentials"""
        self.client_credentials_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret
        )
        self.sp = spotipy.Spotify(client_credentials_manager=self.client_credentials_manager)
    
    def search_track(self, title: str, artist: str) -> Optional[Dict]:
        """
        Search for a track on Spotify using multiple queries + fuzzy ranking.
        Focus on the primary artist and tolerate feature/formatting noise.
        """
        try:
            cleaned_title = self._clean_title(title)
            primary_artist = self._primary_artist(artist)

            queries = [
                f'track:"{cleaned_title}" artist:"{primary_artist}"',
                f'"{cleaned_title}" "{primary_artist}"',
                f'"{cleaned_title}"',
            ]

            best_match = self._find_best_match(queries, cleaned_title, primary_artist)

            if not best_match or best_match[0] < 60:
                logger.warning(f"No strong match for: {title} by {artist} (best_score={best_match[0] if best_match else 'n/a'})")
                return None

            track = best_match[1]
            track_data = self._build_track_payload(track)

            logger.info(f"Found track: {title} by {artist} (score={best_match[0]:.1f})")
            return track_data

        except Exception as e:
            logger.error(f"Error searching for track '{title}' by '{artist}': {e}")
            return None
    
    def enrich_songs(self, songs: List[Dict[str, str]]) -> List[Dict]:
        """
        Enrich a list of songs with Spotify data
        
        Args:
            songs: List of dictionaries with 'title' and 'artist' keys
            
        Returns:
            List of enriched song dictionaries
        """
        enriched_songs = []
        
        for song in songs:
            try:
                track_data = self.search_track(song['title'], song['artist'])
                if track_data:
                    enriched_songs.append(track_data)
                else:
                    # If not found, create a basic entry
                    enriched_songs.append({
                        'id': None,
                        'title': song['title'],
                        'artist': song['artist'],
                        'album': 'Unknown Album',
                        'album_art': None,
                        'preview_url': None,
                        'spotify_url': None,
                        'release_year': None,
                        'duration_ms': None,
                        'duration_formatted': None
                    })
            except Exception as e:
                logger.error(f"Error enriching song {song}: {e}")
                # Add basic entry on error
                enriched_songs.append({
                    'id': None,
                    'title': song['title'],
                    'artist': song['artist'],
                    'album': 'Unknown Album',
                    'album_art': None,
                    'preview_url': None,
                    'spotify_url': None,
                    'release_year': None,
                    'duration_ms': None,
                    'duration_formatted': None
                })
        
        logger.info(f"Enriched {len(enriched_songs)} songs with Spotify data")
        return enriched_songs

    def _clean_title(self, text: str) -> str:
        """Normalize song titles by removing feature/suffix noise for better matching."""
        text = text or ""
        lowered = text.lower()
        lowered = re.sub(r"\s*[\(\[].*?[\)\]]", "", lowered)  # drop parenthetical info
        lowered = re.sub(r"\s*-\s*(remaster(ed)?(?: \d{4})?|live.*|single mix|radio edit).*", "", lowered)
        lowered = re.sub(r"\s*(feat\.?|ft\.?|featuring|with)\s+.*", "", lowered)
        lowered = re.sub(r"\s+", " ", lowered)
        return lowered.strip()

    def _primary_artist(self, artist: str) -> str:
        """Extract primary artist, ignoring featured collaborators."""
        artist = artist or ""
        parts = re.split(r"\s*(,|&|/| x | ft\.?| feat\.?| featuring )\s*", artist, maxsplit=1, flags=re.IGNORECASE)
        return parts[0].strip()

    def _find_best_match(self, queries: List[str], cleaned_title: str, primary_artist: str):
        """Run multiple queries and return the best-scoring track candidate."""
        best_match = None  # (score, track)
        for query in queries:
            results = self.sp.search(q=query, type="track", limit=5, market="US")
            for track in results.get("tracks", {}).get("items", []):
                score = self._score_candidate(cleaned_title, primary_artist, track)
                if not best_match or score > best_match[0]:
                    best_match = (score, track)
            if best_match and best_match[0] >= 80:
                break  # good enough, stop early
        return best_match

    def _score_candidate(self, cleaned_title: str, primary_artist: str, track: Dict) -> float:
        """Score a Spotify track candidate based on title similarity and artist match."""
        track_title = self._clean_title(track.get("name", ""))
        track_artists = [a.get("name", "").lower() for a in track.get("artists", [])]

        title_score = SequenceMatcher(None, cleaned_title, track_title).ratio() * 100

        artist_score = 0
        if track_artists:
            if primary_artist.lower() == track_artists[0]:
                artist_score += 50  # strongest: primary artist matches lead
            if primary_artist.lower() in track_artists:
                artist_score += 20  # primary artist appears anywhere

        return title_score + artist_score

    def _build_track_payload(self, track: Dict) -> Dict:
        """Shape Spotify track data into our response schema."""
        return {
            'id': track.get('id'),
            'title': track.get('name'),
            'artist': track.get('artists', [{}])[0].get('name') if track.get('artists') else None,
            'album': track.get('album', {}).get('name') if track.get('album') else None,
            'album_art': (track.get('album', {}).get('images', [{}])[0].get('url')
                          if track.get('album') and track.get('album', {}).get('images') else None),
            'preview_url': track.get('preview_url'),
            'spotify_url': track.get('external_urls', {}).get('spotify') if track.get('external_urls') else None,
            'release_year': (track.get('album', {}).get('release_date', '')[:4]
                             if track.get('album', {}).get('release_date') else None),
            'duration_ms': track.get('duration_ms'),
            'duration_formatted': self._format_duration(track.get('duration_ms'))
        }
    
    def _format_duration(self, duration_ms: int) -> str:
        """Convert milliseconds to MM:SS format"""
        if not duration_ms:
            return None
        
        seconds = duration_ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        
        return f"{minutes}:{seconds:02d}"
    
    def test_connection(self) -> bool:
        """Test if Spotify API is working"""
        try:
            # Try a simple search
            results = self.sp.search(q="test", type='track', limit=1)
            return True
        except Exception as e:
            logger.error(f"Spotify connection test failed: {e}")
            return False



