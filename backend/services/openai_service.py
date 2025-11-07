import openai
from typing import List, Dict
import json
import logging

logger = logging.getLogger(__name__)

class OpenAIService:
    """Service for interacting with OpenAI GPT-4o-mini API"""
    
    def __init__(self, api_key: str):
        """Initialize OpenAI client with API key"""
        self.client = openai.OpenAI(api_key=api_key)
    
    def get_song_suggestions(self, text_description: str, num_songs: int = 10) -> List[Dict[str, str]]:
        """
        Get song suggestions based on text description
        
        Args:
            text_description: User's description of desired music
            num_songs: Number of songs to return (default: 10)
            
        Returns:
            List of dictionaries with 'title' and 'artist' keys
        """
        try:
            prompt = f"""
            Based on this description: "{text_description}"
            
            Suggest {num_songs} songs that match this description. 
            Return ONLY a valid JSON array of objects with "title" and "artist" fields.
            Make sure the songs are real, popular tracks that would be available on Spotify.
            
            Example format:
            [
                {{"title": "Song Title", "artist": "Artist Name"}},
                {{"title": "Another Song", "artist": "Another Artist"}}
            ]
            
            Focus on songs that match the mood, genre, or activity described.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a music expert who suggests songs based on descriptions. Always return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            # Extract and parse the JSON response
            content = response.choices[0].message.content.strip()
            
            # Try to extract JSON from the response
            if content.startswith('```json'):
                content = content[7:-3]  # Remove ```json and ```
            elif content.startswith('```'):
                content = content[3:-3]  # Remove ``` and ```
            
            songs = json.loads(content)
            
            # Validate the structure
            if not isinstance(songs, list):
                raise ValueError("Response is not a list")
            
            for song in songs:
                if not isinstance(song, dict) or 'title' not in song or 'artist' not in song:
                    raise ValueError("Invalid song structure")
            
            logger.info(f"Successfully got {len(songs)} song suggestions from OpenAI")
            return songs
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from OpenAI response: {e}")
            raise ValueError("Invalid JSON response from OpenAI")
        except Exception as e:
            logger.error(f"Error getting song suggestions from OpenAI: {e}")
            raise Exception(f"OpenAI API error: {str(e)}")
    
    def test_connection(self) -> bool:
        """Test if OpenAI API is working"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Say 'test successful'"}],
                max_tokens=10
            )
            return True
        except Exception as e:
            logger.error(f"OpenAI connection test failed: {e}")
            return False


