import openai
from typing import List, Dict, Any, Optional
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

    def analyze_mood(
        self,
        text_description: str,
        emojis: Optional[List[str]] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fast mood/constraint analysis. Returns {"analysis": {...}} with same shape as before.
        """
        try:
            emoji_context = (
                f'Emoji tags selected by the user: [{", ".join(emojis)}].'
                if emojis else "No emoji tags provided by the user."
            )

            prompt = f"""
            Analyze the mood and constraints for this request: "{text_description}"
            {emoji_context}

            Return ONLY valid JSON:
            {{
              "analysis": {{
                "mood": "1-4 words mood or vibe",
                "matched_criteria": ["genre: ...", "artist: ...", "activity: ..."]
              }}
            }}

            Rules: keep it concise, infer mood from text/emojis, include genre/artist/activity tags when present, no extra text.
            """

            def _run_analysis(max_tokens: int):
                return self.client.chat.completions.create(
                    model=(model or "gemini-2.5-flash"),
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a concise music mood analyzer. Always return valid JSON with an 'analysis' object only.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.4,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                )

            response = _run_analysis(512)
            choice = response.choices[0]
            content = choice.message.content

            if content is None or choice.finish_reason == "length":
                logger.info("Gemini analysis retry triggered (content missing or length finish).")
                response = _run_analysis(1024)
                choice = response.choices[0]
                content = choice.message.content

            if content is None:
                raise ValueError("There was an error processing the Gemini request, try a different request.")
            analysis = self._extract_json(content).get("analysis", {})
            if not isinstance(analysis, dict):
                raise ValueError("Invalid analysis structure from Gemini")

            return {"analysis": analysis}

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Gemini analysis: {e}")
            raise ValueError("Invalid JSON response from Gemini")
        except Exception as e:
            logger.error(f"Error getting mood analysis from Gemini: {e}")
            raise Exception(f"Gemini API error: {str(e)}")

    def recommend_songs(
        self,
        text_description: str,
        analysis: Dict[str, Any],
        num_songs: int = 10,
        emojis: Optional[List[str]] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get song suggestions based on text description and prior analysis.
        Returns {"songs": [...]}. Analysis is passed in, not recomputed.
        """
        try:
            emoji_context = (
                f'Emoji tags selected by the user: [{", ".join(emojis)}]. '
                "Use them as mood/energy/activity cues."
                if emojis else "No emoji tags provided by the user."
            )
            analysis_json = json.dumps(analysis or {}, ensure_ascii=False)

            prompt = f"""
            User request: "{text_description}"
            {emoji_context}
            Prior analysis JSON: {analysis_json}

            Using that analysis, suggest {num_songs} real, popular songs available on Spotify.
            Prioritize the mood/criteria first, then any explicit genres or artists.

            Return ONLY valid JSON:
            {{
              "songs": [
                {{"title": "Song Title", "artist": "Artist Name", "why": "super short reason", "matched_criteria": ["genre: ...", "artist: ..."]}},
                {{"title": "Another Song", "artist": "Another Artist"}}
              ]
            }}

            Rules: keep 'why' brief, keep matched_criteria as short tags, ensure songs are real and likely on Spotify, no extra text.
            """

            def _run_recommendation(max_tokens: int):
                return self.client.chat.completions.create(
                    model=(model or "gemini-2.5-flash"),
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a music expert recommender. Use provided analysis and always return valid JSON with a 'songs' array only.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.8,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                )

            response = _run_recommendation(3000)
            choice = response.choices[0]
            content = choice.message.content

            # Retry once if we hit length or got no content
            if content is None or choice.finish_reason == "length":
                logger.info("Gemini recommendation retry triggered (content missing or length finish).")
                response = _run_recommendation(4000)
                choice = response.choices[0]
                content = choice.message.content

            if content is None:
                raise ValueError("There was an error processing the Gemini request, try a different request.")

            parsed = self._extract_json(content)

            songs: List[Dict[str, Any]] = []
            if isinstance(parsed, dict) and 'songs' in parsed:
                songs = parsed.get('songs', [])
            elif isinstance(parsed, list):
                songs = parsed
            else:
                raise ValueError("Response must be an object with 'songs' or a list")

            if not isinstance(songs, list):
                raise ValueError("'songs' must be a list")

            for song in songs:
                if not isinstance(song, dict) or 'title' not in song or 'artist' not in song:
                    raise ValueError("Invalid song structure")

            logger.info(f"Successfully got {len(songs)} song suggestions from Gemini (emojis: {emojis or []})")
            return {'songs': songs}

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Gemini response: {e}")
            raise ValueError("Invalid JSON response from Gemini")
        except Exception as e:
            logger.error(f"Error getting song suggestions from Gemini: {e}")
            raise Exception(f"Gemini API error: {str(e)}")

    def get_song_suggestions(
        self,
        text_description: str,
        num_songs: int = 10,
        emojis: Optional[List[str]] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Backwards-compatible orchestrator: analyze then recommend."""
        analysis_result = self.analyze_mood(text_description, emojis, model)
        songs_result = self.recommend_songs(
            text_description,
            analysis_result.get("analysis", {}),
            num_songs,
            emojis,
            model,
        )
        return {
            "analysis": analysis_result.get("analysis", {}),
            "songs": songs_result.get("songs", []),
        }

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

    def _extract_json(self, content: str) -> Any:
        """Normalize and parse JSON content from Gemini responses."""
        content = content.strip()
        if content.startswith('```json'):
            content = content[7:-3]
        elif content.startswith('```'):
            content = content[3:-3]
        return json.loads(content)
