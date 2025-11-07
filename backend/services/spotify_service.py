import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from typing import List, Dict, Optional
import logging

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
        Search for a track on Spotify and return enriched data
        
        Args:
            title: Song title
            artist: Artist name
            
        Returns:
            Dictionary with track data or None if not found
        """
        try:
            # Search query combining title and artist
            query = f"track:{title} artist:{artist}"
            
            results = self.sp.search(q=query, type='track', limit=1)
            
            if not results['tracks']['items']:
                logger.warning(f"No results found for: {title} by {artist}")
                return None
            
            track = results['tracks']['items'][0]
            
            # Extract relevant data
            track_data = {
                'id': track['id'],
                'title': track['name'],
                'artist': track['artists'][0]['name'],
                'album': track['album']['name'],
                'album_art': track['album']['images'][0]['url'] if track['album']['images'] else None,
                'preview_url': track['preview_url'],
                'spotify_url': track['external_urls']['spotify'],
                'release_year': track['album']['release_date'][:4] if track['album']['release_date'] else None,
                'duration_ms': track['duration_ms'],
                'duration_formatted': self._format_duration(track['duration_ms'])
            }
            
            logger.info(f"Found track: {title} by {artist}")
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



