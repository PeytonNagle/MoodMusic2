"""
Ollama service for local/remote LLM-based mood analysis and song recommendations.

This service provides an alternative to Gemini using Ollama for local inference.
It supports any Ollama model and can connect to localhost or remote Ollama servers.
"""

import ollama
from typing import List, Dict, Any, Optional
import json
import logging
from .base_mood_service import BaseMoodService

logger = logging.getLogger(__name__)


class OllamaService(BaseMoodService):
    """Service for interacting with Ollama (local/remote LLM inference)"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Ollama client with configuration.

        Args:
            config: Configuration dict with keys:
                - base_url: Ollama server URL (default: http://localhost:11434)
                - model: Model name (default: llama3.2:1b)
                - temperatures: Dict with analysis/recommendations temps
                - token_limits: Dict with token limits for each operation
                - timeout: Request timeout in seconds
                - keep_alive: Model keep-alive duration (e.g., "5m")
        """
        super().__init__(config)

        # Extract config with defaults
        base_url = self.config.get('base_url', 'http://localhost:11434')
        self.model = self.config.get('model', 'llama3.2:1b')
        self.timeout = self.config.get('timeout', 30)
        self.keep_alive = self.config.get('keep_alive', '5m')

        # Initialize Ollama client
        self.client = ollama.Client(host=base_url)

        logger.info(f"Initialized OllamaService: model={self.model}, base_url={base_url}")

    def analyze_mood(
        self,
        text_description: str,
        emojis: Optional[List[str]] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fast mood/constraint analysis using Ollama.

        Args:
            text_description: User's mood description
            emojis: Optional list of emoji characters
            model: Optional model override

        Returns:
            Dict with structure: {"analysis": {"mood": "...", "matched_criteria": [...]}}
        """
        try:
            emoji_context = (
                f'Emoji tags: [{", ".join(emojis)}].'
                if emojis else "No emoji tags provided."
            )

            # Simpler, more directive prompt for smaller models
            prompt = f"""Analyze the mood for this music request: "{text_description}"
{emoji_context}

Return ONLY this JSON format (no other text):
{{
  "analysis": {{
    "mood": "brief mood description (1-4 words)",
    "matched_criteria": ["genre: rock", "artist: specific artist", "activity: workout"]
  }}
}}

Keep mood concise. Include genre/artist/activity tags when mentioned in the request."""

            def _run_analysis(max_tokens: int):
                response = self.client.chat(
                    model=(model or self.model),
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a music mood analyzer. Return ONLY valid JSON with an 'analysis' object. No other text."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    format='json',  # Force JSON output
                    options={
                        'temperature': self.config.get('temperatures', {}).get('analysis', 0.3),
                        'num_predict': max_tokens,
                    },
                    keep_alive=self.keep_alive,
                )
                return response

            # Try initial token limit
            initial_tokens = self.config.get('token_limits', {}).get('analysis_initial', 400)
            response = _run_analysis(initial_tokens)
            content = response.get('message', {}).get('content', '')

            # Retry with higher token limit if needed
            if not content or response.get('done_reason') == 'length':
                logger.info("Ollama analysis retry triggered (empty or length finish).")
                retry_tokens = self.config.get('token_limits', {}).get('analysis_retry', 800)
                response = _run_analysis(retry_tokens)
                content = response.get('message', {}).get('content', '')

            if not content:
                raise ValueError("Empty response from Ollama")

            parsed = self._extract_json(content)
            analysis = parsed.get("analysis", {})

            if not isinstance(analysis, dict):
                raise ValueError("Invalid analysis structure from Ollama")

            return {"analysis": analysis}

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Ollama analysis: {e} | raw={content!r}")
            raise ValueError("Invalid JSON response from Ollama")
        except Exception as e:
            logger.error(f"Error getting mood analysis from Ollama: {e}")
            raise Exception(f"Ollama API error: {str(e)}")

    def recommend_songs(
        self,
        text_description: str,
        analysis: Dict[str, Any],
        num_songs: int = 10,
        emojis: Optional[List[str]] = None,
        model: Optional[str] = None,
        min_popularity: Optional[int] = None,
        popularity_label: Optional[str] = None,
        token_cap: int = 8000,  # Lower default for Ollama
    ) -> Dict[str, Any]:
        """
        Get song recommendations using Ollama.

        Args:
            text_description: User's mood description
            analysis: Mood analysis result from analyze_mood()
            num_songs: Number of songs to recommend
            emojis: Optional list of emoji characters
            model: Optional model override
            min_popularity: Minimum Spotify popularity score
            popularity_label: Human-readable popularity category
            token_cap: Maximum tokens for response

        Returns:
            Dict with structure: {"songs": [{"title": "...", "artist": "...", "why": "...", "matched_criteria": [...]}, ...]}
        """
        try:
            emoji_context = (
                f'Emoji tags: [{", ".join(emojis)}]. Use as mood/energy cues.'
                if emojis else "No emoji tags provided."
            )

            analysis_json = json.dumps(analysis or {}, ensure_ascii=False)

            # Popularity hint
            if popularity_label or min_popularity is not None:
                target_low = min_popularity if min_popularity is not None else 0
                target_high = min(100, (target_low or 0) + 20)
                popularity_hint = f"\nTarget popularity: '{popularity_label}' (Spotify score {target_low}-{target_high}). Don't over-index on chart-toppers if band is lower."
            else:
                popularity_hint = "\nPopularity: any level is fine."

            # More explicit JSON example for smaller models
            prompt = f"""User request: "{text_description}"
{emoji_context}
Prior analysis: {analysis_json}

Suggest exactly {num_songs} songs available on Spotify that match the mood/criteria.{popularity_hint}

Return ONLY this JSON format (no other text):
{{
  "songs": [
    {{"title": "Song Title", "artist": "Artist Name", "why": "brief reason", "matched_criteria": ["genre: rock", "activity: workout"]}},
    {{"title": "Another Song", "artist": "Another Artist", "why": "brief reason", "matched_criteria": []}}
  ]
}}

Requirements:
- Exactly {num_songs} songs
- Real songs available on Spotify
- Keep "why" very brief (5-10 words)
- Keep matched_criteria as short tags
- ONLY output the JSON, no other text"""

            # Calculate token budget
            base_tokens = self.config.get('token_limits', {}).get('recommendations_base', 1500)
            per_song_tokens = self.config.get('token_limits', {}).get('recommendations_per_song', 120)
            recommendations_cap = self.config.get('token_limits', {}).get('recommendations_cap', token_cap)
            max_tokens = min(base_tokens + num_songs * per_song_tokens, recommendations_cap)

            # Higher temperature for lower popularity bands
            low_pop_labels = {"Growing", "Rising", "Under the Radar"}
            temp_low = self.config.get('temperatures', {}).get('recommendations_low_popularity', 0.85)
            temp_standard = self.config.get('temperatures', {}).get('recommendations_standard', 0.7)
            temperature = temp_low if popularity_label in low_pop_labels else temp_standard

            response = self.client.chat(
                model=(model or self.model),
                messages=[
                    {
                        "role": "system",
                        "content": "You are a music expert. Return ONLY valid JSON with a 'songs' array. No other text."
                    },
                    {"role": "user", "content": prompt}
                ],
                format='json',
                options={
                    'temperature': temperature,
                    'num_predict': max_tokens,
                },
                keep_alive=self.keep_alive,
            )

            content = response.get('message', {}).get('content', '')
            if not content:
                raise ValueError("Empty response from Ollama")

            try:
                parsed = self._extract_json_with_salvage(content)
            except Exception:
                # Last-ditch salvage to last complete song
                trimmed = self._salvage_to_last_complete_song(content)
                parsed = self._extract_json(trimmed)

            # Extract songs list
            songs: List[Dict[str, Any]] = []
            if isinstance(parsed, dict) and 'songs' in parsed:
                songs = parsed.get('songs', [])
            elif isinstance(parsed, list):
                songs = parsed
            else:
                raise ValueError("Response must be an object with 'songs' or a list")

            if not isinstance(songs, list):
                raise ValueError("'songs' must be a list")

            # Validate and deduplicate songs
            valid_songs: List[Dict[str, Any]] = []
            seen_keys = set()
            for song in songs:
                if not isinstance(song, dict) or 'title' not in song or 'artist' not in song:
                    continue

                # Deduplication key
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

            logger.info(f"Successfully got {len(valid_songs)} song suggestions from Ollama (emojis: {emojis or []})")
            return {'songs': valid_songs}

        except Exception as e:
            logger.error(f"Error getting song suggestions from Ollama: {e}")
            raise Exception(f"Ollama API error: {str(e)}")

    def test_connection(self) -> bool:
        """Test if Ollama server is reachable and model is available."""
        try:
            # Simple test request
            response = self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                options={'num_predict': 10},
            )
            return bool(response.get('message', {}).get('content'))
        except Exception as e:
            logger.error(f"Ollama connection test failed: {e}")
            return False

