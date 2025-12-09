
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
            logger.error(f"Failed to parse JSON from Gemini analysis: {e} | raw={content!r}")
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
        min_popularity: Optional[int] = None,
        popularity_label: Optional[str] = None,
        token_cap: int = 12000,
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
            if popularity_label or min_popularity is not None:
                target_low = min_popularity if min_popularity is not None else 0
                target_high = min(100, (target_low or 0) + 20)
                popularity_hint = f" Aim for the requested popularity band: '{popularity_label}' (around Spotify {target_low}-{target_high}). Do NOT over-index on chart-toppers if the band is lower."
            else:
                popularity_hint = " Popularity is open; you may choose any songs."

            prompt = f"""
            User request: "{text_description}"
            {emoji_context}
            Prior analysis JSON: {analysis_json}

            Using that analysis, suggest exactly {num_songs} songs available on Spotify.
            Prioritize the mood/criteria first, then any explicit genres or artists.{popularity_hint}

            Return ONLY valid JSON:
            {{
              "songs": [
                {{"title": "Song Title", "artist": "Artist Name", "why": "super short reason", "matched_criteria": ["genre: ...", "artist: ..."]}},
                {{"title": "Another Song", "artist": "Another Artist"}}
              ]
            }}

            Rules: keep 'why' brief, keep matched_criteria as short tags, no extra text.
            """

            # Scale token budget to requested song count; lean higher to reduce truncation
            base_tokens = 2000
            per_song_tokens = 160
            initial_tokens = min(base_tokens + num_songs * per_song_tokens, token_cap)
            current_tokens = initial_tokens

            # Slightly higher temperature for lower popularity bands to encourage variety
            low_pop_labels = {"Growing", "Rising", "Under the Radar"}
            temperature = 0.9 if popularity_label in low_pop_labels else 0.8

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
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                )

            # Single request; salvage and return whatever is valid (trimmed to num_songs)
            response = _run_recommendation(current_tokens)
            choice = response.choices[0]
            content = choice.message.content
            if content is None:
                raise ValueError("Empty response from Gemini")

            try:
                parsed = self._extract_json_with_salvage(content)
            except Exception:
                # Last-ditch salvage to last complete song
                trimmed = self._salvage_to_last_complete_song(content or "")
                parsed = self._extract_json(trimmed)

            songs: List[Dict[str, Any]] = []
            if isinstance(parsed, dict) and 'songs' in parsed:
                songs = parsed.get('songs', [])
            elif isinstance(parsed, list):
                songs = parsed
            else:
                raise ValueError("Response must be an object with 'songs' or a list")

            if not isinstance(songs, list):
                raise ValueError("'songs' must be a list")

            valid_songs: List[Dict[str, Any]] = []
            seen_keys = set()
            for song in songs:
                if not isinstance(song, dict) or 'title' not in song or 'artist' not in song:
                    continue
                key = f"{str(song.get('title', '')).strip().lower()}|{str(song.get('artist', '')).strip().lower()}"
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                valid_songs.append(song)
                if len(valid_songs) >= num_songs:
                    break

            if not valid_songs:
                logger.warning("No valid songs after parsing/salvage; returning empty list.")
                return {'songs': []}

            logger.info(f"Successfully got {len(valid_songs)} song suggestions from Gemini (emojis: {emojis or []})")
            return {'songs': valid_songs}

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

    def _extract_json_with_salvage(self, content: str) -> Any:
        """Parse JSON and attempt a light repair on failure."""
        try:
            return self._extract_json(content)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse failed; trimming to last complete song. error={e}")
            repaired = self._salvage_to_last_complete_song(content)
            parsed = self._extract_json(repaired)
            logger.info("JSON salvage succeeded using trimmed payload.")
            return parsed

    def _extract_json(self, content: str) -> Any:
        """Normalize and parse JSON content from Gemini responses."""
        content = content.strip()
        if content.startswith('```json'):
            content = content[7:-3]
        elif content.startswith('```'):
            content = content[3:-3]
        return json.loads(content)

    def _salvage_to_last_complete_song(self, content: str) -> str:
        """
        Trim the payload back to the last complete song object and close the JSON.
        """
        text = content.strip()
        if text.startswith('```json'):
            text = text[7:-3]
        elif text.startswith('```'):
            text = text[3:-3]

        last_brace = text.rfind('}')
        if last_brace == -1:
            return text

        text = text[: last_brace + 1]
        text = text.rstrip(', \n\r\t')

        # Drop a trailing comma before closing the array/object
        if text.endswith(','):
            text = text.rstrip(', \n\r\t')

        if '"songs"' in text and '[' in text and not text.strip().endswith((']', ']}', '}}')):
            text += "\n  ]\n}"
        return text
