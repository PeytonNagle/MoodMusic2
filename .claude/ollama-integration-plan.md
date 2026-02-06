# Implementation Plan: Ollama Integration with Configurable LLM Support

## Overview

Add Ollama as an alternative AI provider to Gemini for mood analysis and song recommendations. The system will support configuration-driven provider selection while maintaining backward compatibility with the existing Gemini integration.

**User Requirements:**
- Keep `gemini_service.py` working (no breaking changes)
- Maintain identical API interface
- Support any Ollama model (configurable, starting with llama3.2:1b)
- Support both localhost and remote Ollama deployments
- Single provider mode (no fallback complexity)
- Future: RAG integration for trending/new song recommendations

## Architecture

### Provider Abstraction Pattern

Create an abstract base class `BaseMoodService` that defines the service contract:
- `analyze_mood(text, emojis, model)` → `{"analysis": {...}}`
- `recommend_songs(text, analysis, num_songs, ...)` → `{"songs": [...]}`
- `test_connection()` → `bool`

Both `GeminiService` and `OllamaService` will inherit from this base class, ensuring identical interfaces.

### Configuration-Driven Provider Selection

Provider selection via:
1. **Environment variable** (highest priority): `AI_PROVIDER=ollama` or `AI_PROVIDER=gemini`
2. **JSON config** (fallback): `ai_provider.default` in config files

Different environments can use different defaults:
- **Dev**: Ollama (fast local iteration)
- **Production**: Gemini (reliable cloud API)

### File Structure

```
backend/services/
├── base_mood_service.py        # Abstract base class (NEW)
├── ollama_service.py           # Ollama implementation (NEW)
├── service_factory.py          # Factory pattern for provider instantiation (NEW)
├── gemini_service.py           # Refactored to inherit from base (MODIFY)
└── spotify_service.py          # Unchanged

backend/
├── app.py                      # Use factory for service creation (MODIFY)
├── config.py                   # Add AI_PROVIDER env var + validation (MODIFY)
└── configs/
    ├── config.json             # Add ai_provider section (MODIFY)
    ├── config.dev.json         # Set default to ollama (MODIFY)
    └── config.prod.json        # Set default to gemini (MODIFY)
```

## Implementation Steps

### Step 1: Create Abstract Base Class

**File**: `backend/services/base_mood_service.py` (NEW)

Define the service interface contract:

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseMoodService(ABC):
    """Abstract base class for mood analysis and song recommendation services."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    @abstractmethod
    def analyze_mood(
        self, text_description: str, emojis: Optional[List[str]] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Returns {"analysis": {"mood": "...", "matched_criteria": [...]}}"""
        pass

    @abstractmethod
    def recommend_songs(
        self, text_description: str, analysis: Dict[str, Any], num_songs: int = 10,
        emojis: Optional[List[str]] = None, model: Optional[str] = None,
        min_popularity: Optional[int] = None, popularity_label: Optional[str] = None,
        token_cap: int = 12000
    ) -> Dict[str, Any]:
        """Returns {"songs": [{"title": "...", "artist": "...", ...}]}"""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Test if the service is available."""
        pass

    def get_song_suggestions(
        self, text_description: str, num_songs: int = 10,
        emojis: Optional[List[str]] = None, model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Backward-compatible orchestrator method."""
        analysis_result = self.analyze_mood(text_description, emojis, model)
        songs_result = self.recommend_songs(
            text_description, analysis_result.get("analysis", {}),
            num_songs, emojis, model
        )
        return {
            "analysis": analysis_result.get("analysis", {}),
            "songs": songs_result.get("songs", [])
        }
```

**Why**: Enforces consistent interface, enables dependency injection with type safety, makes testing easier.

### Step 2: Refactor GeminiService to Inherit from Base

**File**: `backend/services/gemini_service.py` (MODIFY)

Add inheritance (minimal change):

```python
from .base_mood_service import BaseMoodService

class GeminiService(BaseMoodService):
    """Service for interacting with Google Gemini via OpenAI-compatible API"""

    def __init__(self, api_key: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)  # NEW: Call base constructor
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        # Rest of __init__ unchanged (self.config already set by parent)

    # All other methods unchanged - they already match the interface
```

**Impact**: Single line added (`super().__init__(config)`), no functional changes.

### Step 3: Implement OllamaService

**File**: `backend/services/ollama_service.py` (NEW)

Full implementation mirroring GeminiService structure but adapted for Ollama:

**Key differences from Gemini:**
- Uses `ollama.Client` instead of `openai.OpenAI`
- No API key required (local/remote server)
- Configurable base_url (localhost or remote)
- `format='json'` parameter forces JSON output
- Simpler prompts optimized for smaller models
- Lower default token limits (8K cap vs 12K)
- Lower temperatures for consistency

**Prompt engineering for smaller models:**
- More explicit JSON schema examples
- Clearer, more directive instructions
- Shorter prompts (smaller context windows)
- Emphasis on "ONLY output JSON, no other text"

**Error handling:**
- Same salvage logic as Gemini (`_salvage_to_last_complete_song()`)
- Handles truncated responses gracefully
- Deduplication and validation identical to Gemini

See detailed implementation in the Plan agent output (omitted here for brevity, but includes full `analyze_mood()`, `recommend_songs()`, and helper methods).

### Step 4: Create Service Factory

**File**: `backend/services/service_factory.py` (NEW)

Factory pattern for creating service instances:

```python
import logging
from typing import Optional
from .base_mood_service import BaseMoodService
from .gemini_service import GeminiService
from .ollama_service import OllamaService

logger = logging.getLogger(__name__)

class MoodServiceFactory:
    """Factory for creating mood analysis service instances."""

    @staticmethod
    def create_service(
        provider: str,
        gemini_api_key: Optional[str] = None,
        gemini_config: Optional[dict] = None,
        ollama_config: Optional[dict] = None,
    ) -> Optional[BaseMoodService]:
        """
        Create a mood service instance based on provider name.

        Args:
            provider: 'gemini' or 'ollama'
            gemini_api_key: API key for Gemini (required if provider='gemini')
            gemini_config: Configuration dict for GeminiService
            ollama_config: Configuration dict for OllamaService

        Returns:
            BaseMoodService instance or None if provider cannot be initialized
        """
        provider = provider.lower().strip()

        if provider == 'gemini':
            if not gemini_api_key:
                logger.error("Gemini provider selected but GEMINI_API_KEY not set")
                return None
            logger.info("Creating GeminiService instance")
            return GeminiService(gemini_api_key, gemini_config)

        elif provider == 'ollama':
            logger.info("Creating OllamaService instance")
            return OllamaService(ollama_config)

        else:
            raise ValueError(f"Unknown AI provider: {provider}. Must be 'gemini' or 'ollama'.")
```

**Usage**: `mood_service = MoodServiceFactory.create_service('ollama', ollama_config={...})`

### Step 5: Update Configuration System

#### 5.1 Add ai_provider Section to Base Config

**File**: `backend/configs/config.json` (MODIFY)

Add new top-level section:

```json
{
  "version": "1.0.0",
  "ai_provider": {
    "default": "gemini",
    "ollama": {
      "base_url": "http://localhost:11434",
      "model": "llama3.2:1b",
      "temperatures": {
        "analysis": 0.3,
        "recommendations_standard": 0.7,
        "recommendations_low_popularity": 0.85
      },
      "token_limits": {
        "analysis_initial": 400,
        "analysis_retry": 800,
        "recommendations_base": 1500,
        "recommendations_per_song": 120,
        "recommendations_cap": 8000
      },
      "timeout": 30,
      "keep_alive": "5m"
    }
  },
  "request_handling": { ... },
  "gemini": { ... }
}
```

**Rationale for Ollama-specific settings:**
- **Lower temperatures**: Smaller models need more conservative sampling
- **Smaller token limits**: Prevent truncation on smaller context windows
- **Configurable base_url**: Support both localhost and remote deployments
- **keep_alive**: Keep model loaded in memory for faster subsequent requests

#### 5.2 Environment-Specific Overrides

**File**: `backend/configs/config.dev.json` (MODIFY)

```json
{
  "ai_provider": {
    "default": "ollama"
  }
}
```

**Rationale**: Dev uses local Ollama for faster iteration (no API latency/costs).

**File**: `backend/configs/config.prod.json` (MODIFY)

```json
{
  "ai_provider": {
    "default": "gemini"
  }
}
```

**Rationale**: Production uses reliable cloud Gemini API.

#### 5.3 Update Config Class

**File**: `backend/config.py` (MODIFY)

Add environment variable and helper methods:

```python
class Config:
    # Existing API Keys
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
    SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')

    # NEW: AI Provider settings
    AI_PROVIDER = os.getenv('AI_PROVIDER')  # Override config if set
    OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL')  # Override config if set

    # ... existing code ...

    @classmethod
    def get_ai_provider(cls) -> str:
        """Get the active AI provider name (gemini or ollama)."""
        if cls.AI_PROVIDER:
            return cls.AI_PROVIDER.lower()
        return cls.get('ai_provider.default', 'gemini').lower()

    @staticmethod
    def validate_config():
        """Validate required API keys based on active provider."""
        provider = Config.get_ai_provider()

        required_vars = [
            ('SPOTIPY_CLIENT_ID', Config.SPOTIPY_CLIENT_ID),
            ('SPOTIPY_CLIENT_SECRET', Config.SPOTIPY_CLIENT_SECRET)
        ]

        # Only require Gemini key if using Gemini
        if provider == 'gemini':
            required_vars.append(('GEMINI_API_KEY', Config.GEMINI_API_KEY))

        missing_vars = [name for name, value in required_vars if not value]

        if missing_vars:
            print(f"Warning: Missing environment variables: {', '.join(missing_vars)}")
            return False
        return True
```

**Update ConfigLoader validation** to include `ai_provider` in required sections:

```python
required_sections = [
    'request_handling', 'gemini', 'spotify', 'popularity',
    'database', 'ai_provider'  # NEW
]
```

### Step 6: Update Application Initialization

**File**: `backend/app.py` (MODIFY)

Replace service initialization (lines 33-36):

```python
# OLD:
# gemini_service = GeminiService(
#     Config.GEMINI_API_KEY,
#     Config._config_data.get('gemini')
# ) if Config.GEMINI_API_KEY else None

# NEW:
from services.service_factory import MoodServiceFactory

provider = Config.get_ai_provider()
logger.info(f"Initializing AI provider: {provider}")

# Override base_url if environment variable is set
ollama_config = Config._config_data.get('ai_provider', {}).get('ollama', {})
if Config.OLLAMA_BASE_URL:
    ollama_config = {**ollama_config, 'base_url': Config.OLLAMA_BASE_URL}

mood_service = MoodServiceFactory.create_service(
    provider=provider,
    gemini_api_key=Config.GEMINI_API_KEY,
    gemini_config=Config._config_data.get('gemini'),
    ollama_config=ollama_config,
)

if not mood_service:
    logger.error(f"Failed to initialize AI provider: {provider}")

# Initialize Spotify service (unchanged)
spotify_service = SpotifyService(...) if ... else None
```

**Update blueprint registration** (keep parameter name for backward compat):

```python
register_blueprints(
    app,
    gemini_service=mood_service,  # Name unchanged (now BaseMoodService)
    spotify_service=spotify_service,
    save_queue=save_worker.queue
)
```

**Note**: Controllers receive `BaseMoodService` interface, don't care about implementation.

### Step 7: Update Health Check Endpoint

**File**: `backend/controllers/health_controller.py` (MODIFY)

Show active provider in health check response:

```python
def health_check(self):
    """Health check endpoint."""
    try:
        ai_provider = Config.get_ai_provider()
        ai_status = self.gemini_service.test_connection() if self.gemini_service else False
        spotify_status = self.spotify_service.test_connection() if self.spotify_service else False

        return jsonify({
            'status': 'healthy',
            'services': {
                'ai_provider': ai_provider,  # NEW: shows 'gemini' or 'ollama'
                'ai_service': 'connected' if ai_status else 'disconnected',
                'spotify': 'connected' if spotify_status else 'disconnected'
            },
            'config_loaded': Config.validate_config()
        })
    except Exception as e:
        logger.exception("Health check failed")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500
```

### Step 8: Update Dependencies

**File**: `backend/requirements.txt` (ADD)

```
ollama>=0.4.0
```

**Installation**: `pip install ollama`

### Step 9: Update Documentation

#### Update CLAUDE.md

**File**: `CLAUDE.md` (ADD SECTION)

Add comprehensive AI provider documentation:

```markdown
## AI Provider Configuration

MoodMusic2 supports multiple AI providers for mood analysis and song recommendations.

### Supported Providers
- **Gemini** (default): Google Gemini AI via OpenAI-compatible endpoint
- **Ollama**: Local/remote LLM inference (supports any Ollama model)

### Switching Providers

**Via Environment Variable (highest priority):**
```bash
export AI_PROVIDER=ollama  # or 'gemini'
export OLLAMA_BASE_URL=http://localhost:11434  # optional override
```

**Via Configuration File:**
Edit `backend/configs/config.json` or environment-specific overrides:
```json
{
  "ai_provider": {
    "default": "ollama",
    "ollama": {
      "base_url": "http://your-server:11434",
      "model": "llama3.2:1b"
    }
  }
}
```

### Ollama Setup

**Install Ollama:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Pull a model:**
```bash
ollama pull llama3.2:1b  # Or mistral, llama3.2:3b, etc.
```

**Start Ollama:**
```bash
ollama serve  # Runs on http://localhost:11434
```

**Verify:**
```bash
curl http://localhost:11434/api/tags  # Should list available models
```

### Supported Ollama Models

The system works with any Ollama model. Configure via `ai_provider.ollama.model`:

**Recommended models:**
- `llama3.2:1b` - Fastest, lowest resource usage
- `llama3.2:3b` - Better quality, still fast
- `mistral:7b` - Higher quality, needs more RAM

**Configuration example:**
```json
{
  "ai_provider": {
    "ollama": {
      "model": "mistral:7b"
    }
  }
}
```

### Provider Comparison

| Feature | Gemini | Ollama |
|---------|--------|--------|
| Latency | 500-2000ms (cloud) | 100-500ms (local) |
| Cost | API usage charges | Free (local compute) |
| Quality | High (large model) | Variable (model-dependent) |
| Privacy | Data sent to Google | Fully local |
| Availability | Requires internet | Works offline |
| Setup | API key only | Requires installation |

### Architecture

**Service Abstraction:**
- `BaseMoodService` - Abstract base class defining the interface
- `GeminiService` - Google Gemini implementation
- `OllamaService` - Ollama implementation
- `MoodServiceFactory` - Creates service instances based on configuration

Controllers remain provider-agnostic and work with any `BaseMoodService` implementation.

**Configuration System:**
- Environment variables override JSON config
- Different defaults per environment (dev → ollama, prod → gemini)
- Model-specific tuning (temperatures, token limits)
```

#### Update README.md

**File**: `README.md` (MODIFY)

Update environment variables section and add Ollama setup:

```markdown
### Environment Variables

Create `backend/.env`:

```bash
# AI Provider
AI_PROVIDER=gemini  # or 'ollama' for local inference
GEMINI_API_KEY=your_gemini_api_key  # required if using Gemini
OLLAMA_BASE_URL=http://localhost:11434  # optional, override for remote Ollama

# Spotify (required)
SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret

# Database (optional)
DATABASE_URL=postgresql://user:pass@localhost:5432/moodmusic
ENVIRONMENT=dev  # dev, staging, or prod
```

### Ollama Setup (Optional)

Use local AI inference instead of Gemini:

**Install Ollama:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Pull a model:**
```bash
ollama pull llama3.2:1b
```

**Start Ollama:**
```bash
ollama serve
```

**Configure MoodMusic2:**
```bash
export AI_PROVIDER=ollama
python backend/app.py
```

See [CLAUDE.md](CLAUDE.md#ai-provider-configuration) for advanced configuration.
```

## Future Enhancement: RAG for Trending/New Songs

### Phase 1: Trending Songs from Spotify API (Priority)

**Goal**: Enrich recommendations with current trending songs and new releases.

**Implementation approach:**

1. **Create Spotify Trending Service** (`backend/services/spotify_trending_service.py`):
   - Fetch Spotify "Top 50 Global" playlist
   - Fetch "New Releases" endpoint data
   - Fetch category-specific trending playlists (e.g., "Top Rock", "Hot Hip-Hop")
   - Cache results (refresh every 6-24 hours)

2. **Build Vector Database of Trending Songs**:
   - Use sentence-transformers to create embeddings for song metadata
   - Store: `{song_id, title, artist, genres, mood_tags, embedding, release_date, popularity}`
   - Use FAISS or ChromaDB for fast similarity search

3. **Integrate into Recommendation Flow**:
   - When analyzing mood, generate embedding for user query
   - Retrieve top K similar trending songs from vector DB
   - Inject trending songs into LLM context as "Recently popular songs matching this vibe: [...]"
   - LLM uses both its knowledge + RAG context to recommend

4. **Configuration**:
   ```json
   {
     "rag": {
       "enabled": true,
       "trending_playlists": [
         "spotify:playlist:37i9dQZEVXbMDoHDwVN2tF",  // Global Top 50
         "spotify:playlist:37i9dQZF1DX4JAvHpjipBk"   // New Music Friday
       ],
       "refresh_interval_hours": 12,
       "max_context_songs": 10
     }
   }
   ```

**Benefits**:
- Recommendations include recent hits and new releases
- LLM has up-to-date context beyond training cutoff
- Improves discovery of trending songs matching user mood

### Phase 2: Music News/Reviews Scraping (Future)

**Goal**: Incorporate music blog mentions, reviews, social media buzz.

**Potential sources**:
- Pitchfork, Rolling Stone APIs/RSS feeds
- Reddit music subreddits (r/music, genre-specific)
- Twitter/X trending music hashtags
- Spotify "Discover Weekly" analysis

**Implementation**:
- Scheduled scraping jobs (daily)
- Extract: song mentions, sentiment, context
- Update vector DB with enriched metadata
- Weight recent mentions higher in similarity search

**Challenges**:
- Data quality and noise filtering
- Rate limiting and API access
- Legal/ethical web scraping considerations

### RAG Architecture Diagram

```
User Query → [Embedding Model] → Vector Search → Top K Trending Songs
                     ↓
              [Mood Analysis] ← RAG Context Injection
                     ↓
           [Song Recommendation] → Spotify Enrichment → Results
```

## Testing Strategy

### Unit Tests

Create test files:
- `backend/tests/test_base_mood_service.py` - Test abstract interface
- `backend/tests/test_ollama_service.py` - Mock Ollama client responses
- `backend/tests/test_service_factory.py` - Test factory creation logic

### Integration Tests

**Manual testing checklist:**
1. ✅ Start Ollama: `ollama serve`
2. ✅ Pull model: `ollama pull llama3.2:1b`
3. ✅ Verify: `curl http://localhost:11434/api/tags`
4. ✅ Set env: `export AI_PROVIDER=ollama`
5. ✅ Start backend: `python backend/app.py`
6. ✅ Check health: `curl http://localhost:5000/api/health`
   - Should show `"ai_provider": "ollama"`
   - Should show `"ai_service": "connected"`
7. ✅ Test search: `POST /api/search` with sample query
8. ✅ Verify response format matches Gemini
9. ✅ Switch to `AI_PROVIDER=gemini` and repeat
10. ✅ Test remote Ollama: `export OLLAMA_BASE_URL=http://remote-server:11434`

### Performance Testing

Compare Gemini vs Ollama:
- Latency for analysis (target: <500ms for Ollama)
- Latency for recommendations (target: <2s for Ollama)
- Response quality (manual evaluation)
- Accuracy of JSON parsing/salvage logic

## Rollout Plan

### Phase 1: Foundation (1-2 hours)
- [ ] Create `base_mood_service.py`
- [ ] Refactor `gemini_service.py` to inherit
- [ ] Test Gemini still works (no regressions)

### Phase 2: Ollama Implementation (2-3 hours)
- [ ] Implement `ollama_service.py`
- [ ] Create `service_factory.py`
- [ ] Add unit tests

### Phase 3: Configuration (1 hour)
- [ ] Update config files (add `ai_provider` section)
- [ ] Update `config.py` with new methods
- [ ] Test config loading

### Phase 4: Integration (1-2 hours)
- [ ] Update `app.py` to use factory
- [ ] Update health check endpoint
- [ ] Install Ollama locally
- [ ] Pull llama3.2:1b model
- [ ] Test full integration

### Phase 5: Documentation (1 hour)
- [ ] Update CLAUDE.md
- [ ] Update README.md
- [ ] Update requirements.txt
- [ ] Create setup guide

**Total estimated time**: 6-9 hours

## Critical Files Summary

**NEW Files:**
- `backend/services/base_mood_service.py` - Abstract interface (~80 lines)
- `backend/services/ollama_service.py` - Ollama implementation (~300 lines)
- `backend/services/service_factory.py` - Factory pattern (~50 lines)

**MODIFIED Files:**
- `backend/services/gemini_service.py` - Add inheritance (1 line change)
- `backend/app.py` - Replace service init with factory (~10 lines)
- `backend/config.py` - Add AI_PROVIDER env var + helpers (~20 lines)
- `backend/configs/config.json` - Add ai_provider section (~25 lines)
- `backend/configs/config.dev.json` - Override default to ollama (~3 lines)
- `backend/configs/config.prod.json` - Keep default as gemini (~3 lines)
- `backend/controllers/health_controller.py` - Show active provider (~2 lines)
- `backend/requirements.txt` - Add ollama package (1 line)
- `CLAUDE.md` - Add AI provider docs (~100 lines)
- `README.md` - Add Ollama setup section (~30 lines)

## Success Criteria

1. ✅ Gemini integration works unchanged (backward compatibility)
2. ✅ Ollama provides identical API contract
3. ✅ Health endpoint shows active provider
4. ✅ Configuration switching works (env var + JSON)
5. ✅ Documentation includes complete setup guide
6. ✅ Both localhost and remote Ollama deployments supported
7. ✅ Any Ollama model can be configured

## Verification Steps

After implementation:

```bash
# Test Ollama
export AI_PROVIDER=ollama
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "upbeat rock music", "limit": 5}'

# Test Gemini
export AI_PROVIDER=gemini
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "upbeat rock music", "limit": 5}'

# Both should return identical response structure
```
