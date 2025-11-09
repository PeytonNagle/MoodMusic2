import openai
from typing import List, Dict, Any
import json
import logging

logger = logging.getLogger(__name__)


class GeminiService:
    """Service for interacting with Google Gemini via OpenAI-compatible API"""

    def __init__(self, api_key: str):
        """Initialize OpenAI client pointed at Gemini's compatible endpoint"""
        # Gemini OpenAI-compatible endpoint (v1beta)
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )

    def get_song_suggestions(self, text_description: str, num_songs: int = 10) -> Dict[str, Any]:
        """
        Get song suggestions based on text description using Gemini, with mood-first
        interpretation and optional analysis metadata.

        Args:
            text_description: User's description of desired music
            num_songs: Number of songs to return (default: 10)

        Returns:
            Dict with:
              - 'songs': List of dictionaries with at least 'title' and 'artist'
              - 'analysis': Optional dict with keys like 'mood' and 'matched_criteria'
        """
        try:
            prompt = f"""
            Based on this description: "{text_description}"

            Your job:
            1) Infer the primary mood (e.g., "upbeat", "melancholic night drive", "calm focus").
            2) Detect any explicit genres or artists mentioned.
            3) Suggest {num_songs} real, popular songs available on Spotify that match the mood first. If genres or artists are mentioned, include them among your picks while still reflecting the mood.

            Return ONLY a valid JSON object with the following shape:
            {{
              "songs": [
                {{"title": "Song Title", "artist": "Artist Name", "why": "super short reason", "matched_criteria": ["genre: indie rock", "artist: Drake"]}},
                {{"title": "Another Song", "artist": "Another Artist"}}
              ],
              "analysis": {{
                "mood": "inferred mood",
                "matched_criteria": ["genre: ...", "artist: ..."]
              }}
            }}

            Rules:
            - Always prioritize mood when selecting songs.
            - Respect explicit genres or artists by including matching picks where possible.
            - Make sure the songs are real and likely available on Spotify.
            - Always return valid JSON with double quotes and no extra text.
            """

            response = self.client.chat.completions.create(
                model="gemini-2.5-flash",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a music expert. Interpret user text as mood-first, then respect any explicit genres or artists. Always return valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=4000,
            )

            # Extract and parse the JSON response
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("There was an error processing the Gemini request, try a different request.")
            content = content.strip()

            # Try to extract JSON from the response
            if content.startswith('```json'):
                content = content[7:-3]  # Remove ```json and ```
            elif content.startswith('```'):
                content = content[3:-3]  # Remove ``` and ```
            # DEBUG
            print(f"\nJson Response:\n{content}\n")
            parsed = json.loads(content)

            songs: List[Dict[str, Any]] = []
            analysis: Dict[str, Any] = {}

            # Accept either an object with songs/analysis, or a bare list for backward compatibility
            if isinstance(parsed, dict) and 'songs' in parsed:
                songs = parsed.get('songs', [])
                if not isinstance(songs, list):
                    raise ValueError("'songs' must be a list")
                analysis_obj = parsed.get('analysis')
                if isinstance(analysis_obj, dict):
                    analysis = analysis_obj
            elif isinstance(parsed, list):
                songs = parsed
            else:
                raise ValueError("Response must be an object with 'songs' or a list")

            # Validate songs
            for song in songs:
                if not isinstance(song, dict) or 'title' not in song or 'artist' not in song:
                    raise ValueError("Invalid song structure")

            logger.info(f"Successfully got {len(songs)} song suggestions from Gemini")
            return {
                'songs': songs,
                'analysis': analysis
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Gemini response: {e}")
            raise ValueError("Invalid JSON response from Gemini")
        except Exception as e:
            logger.error(f"Error getting song suggestions from Gemini: {e}")
            raise Exception(f"Gemini API error: {str(e)}")

    def test_connection(self) -> bool:
        """Test if Gemini API is working via the compatible endpoint"""
        try:
            _ = self.client.chat.completions.create(
                model="gemini-2.5-flash",
                messages=[{"role": "user", "content": "Say 'test successful'"}],
                max_tokens=10,
            )
            return True
        except Exception as e:
            logger.error(f"Gemini connection test failed: {e}")
            return False
