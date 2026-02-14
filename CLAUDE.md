# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MoodMusic2 is a full-stack application that converts mood descriptions (text + emojis) into Spotify song recommendations using AI for mood analysis and the Spotify API for enrichment.

**Stack:**
- Backend: Flask + PostgreSQL, configurable AI provider (Gemini or Ollama), Spotipy
- Frontend: React + TypeScript, Vite, Tailwind CSS, shadcn/ui components
- AI Providers: Google Gemini (via OpenAI-compatible endpoint) or Ollama (local/remote LLM)

## Development Commands

### Backend (Flask API)
```bash
cd backend
source ../.venv/bin/activate  # Virtual env is at root level
python app.py                  # Runs on http://localhost:5000
```

### Frontend (React + Vite)
```bash
cd frontend
npm install
npm run dev      # Dev server on http://localhost:3000
npm run build    # Production build
npm run preview  # Preview production build
```

### Database Setup (Optional)
Database features are optional. The app works without PostgreSQL for search/recommendations.

```bash
# Initialize database schema (PostgreSQL) for user accounts and history
psql $DATABASE_URL -f backend/scripts/init.sql

# Or use the schema directly
psql $DATABASE_URL -f backend/scripts/schema.sql
```

**Note:** Set `DATABASE_URL` in `.env` and ensure PostgreSQL is running. The backend gracefully handles missing database connections for core features.

## Environment Configuration

### Required Environment Variables

Create `backend/.env` with:
```
# AI Provider (optional, defaults to config file)
AI_PROVIDER=gemini  # or 'ollama' for local inference
GEMINI_API_KEY=your_gemini_api_key  # required if using Gemini
OLLAMA_BASE_URL=http://localhost:11434  # optional, override for remote Ollama

# Spotify (required)
SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret

# Database (optional)
DATABASE_URL=postgresql://user:pass@host:port/dbname  # required for DB features

# Flask (optional)
DEBUG=true
ENVIRONMENT=dev  # dev, staging, or prod (defaults to dev)
```

### JSON Configuration System

The backend uses a layered JSON configuration system (`backend/configs/`):
- `config.json`: Base configuration with all defaults
- `config.{environment}.json`: Environment-specific overrides (dev, staging, prod)
- Configurations are deep-merged, with environment configs overriding base values

Key configuration sections:
- `ai_provider`: Default provider, Ollama settings (model, temperatures, token limits)
- `request_handling`: Emoji limits, song limits, request sizing parameters
- `gemini`: Model selection, temperatures, token limits
- `spotify`: Search parameters, fuzzy matching thresholds
- `popularity`: Tolerance values, category ranges, filtering thresholds
- `database`: Save queue behavior, persistence flags, history limits
- `flask`: Server host, port, debug mode

Access config values in code: `Config.get('path.to.value', default_value)`

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

## Architecture & Key Patterns

### Backend Architecture (Updated 2026-01-24)

The backend follows a **layered controller-service architecture** with dependency injection:

```
app.py (59 lines) - Service initialization & blueprint registration
├── blueprints.py - Route definitions
├── controllers/ - Business logic with injected services
│   ├── SearchController - Search, analyze, recommend endpoints
│   ├── UserController - Registration, login
│   ├── HistoryController - User search history
│   └── HealthController - Health checks
├── services/ - External API integrations
│   ├── gemini_service.py - Gemini AI calls
│   ├── spotify_service.py - Spotify API calls
│   └── requests_utils.py - Request validation
├── workers/ - Background tasks
│   └── save_worker.py - Async database saves
└── db*.py - Database access layer
```

**Key Principles**:
- **Dependency Injection**: Services passed to controllers via constructor
- **Flask Blueprints**: Routes organized by functional area
- **Separation of Concerns**: HTTP handling separate from business logic
- **Testability**: Controllers can be unit tested without Flask context

### Backend Request Flow

1. **Search/Recommend Flow** (`/api/search`, `/api/recommend`):
   - Parse & validate request (query, emojis, limit, popularity constraints) using `services/requests_utils.py`
   - Call `gemini_service.analyze_mood()` for fast mood/constraint analysis
   - Call `gemini_service.recommend_songs()` with analysis + popularity hints
   - Enrich AI recommendations with `spotify_service.enrich_songs()` (fuzzy matching, metadata)
   - Apply popularity filtering with tolerance and deduplication
   - Background worker saves requests/songs to PostgreSQL asynchronously via `SAVE_QUEUE`

2. **Multi-Attempt Strategy**: The `generate_recommendations()` function in `app.py` makes up to 2 Gemini requests, dynamically sizing them based on popularity filtering needs. It uses `compute_first_request_size()` and `compute_second_request_size()` from `requests_utils.py` to calculate how many songs to request.

3. **Popularity System**:
   - Categories: "Global / Superstar" (90-100), "Hot / Established" (75-89), "Buzzing / Moderate" (50-74), "Growing" (25-49), "Rising" (15-24), "Under the Radar" (0-14)
   - Filtering applies tolerance (5 baseline + extra for lower tiers) in `resolve_popularity_constraints()`
   - Backend pads results with unfiltered songs if popularity filter is too strict

### Services Layer

**`services/gemini_service.py`**:
- Uses OpenAI client pointed at `https://generativelanguage.googleapis.com/v1beta/openai/`
- `analyze_mood()`: Returns mood + matched_criteria tags (fast, 512-1024 tokens)
- `recommend_songs()`: Takes analysis + popularity hints, returns song list with title/artist/why/matched_criteria
- Forces JSON output via `response_format={"type": "json_object"}` to reduce parse errors
- Salvage logic (`_salvage_to_last_complete_song()`) trims incomplete JSON on truncation

**`services/spotify_service.py`**:
- `enrich_songs()`: Batch enriches AI recommendations with Spotify metadata
- `search_track()`: Multi-query search with fuzzy scoring (title similarity + primary artist match)
- Cleans titles/artists to ignore features, remasters, parentheticals for better matching
- Returns album art, preview URL, Spotify deep link, release year, duration, popularity score

**`services/requests_utils.py`**:
- Centralized validation logic: `require_json_body()`, `parse_query()`, `parse_emojis()`, `normalize_limit()`
- `compute_first_request_size()` and `compute_second_request_size()` calculate dynamic Gemini request sizing
- Custom `ValidationError` exception for client-facing 400-level errors

**`config.py`**:
- `ConfigLoader`: Loads and deep-merges JSON configs from `backend/configs/`
- `Config`: Static configuration class with dot-notation access via `Config.get('path.to.value', default)`
- Validates required environment variables (`GEMINI_API_KEY`, `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`)
- Supports environment-specific overrides (dev/staging/prod)

### Database Layer

**Schema** (`backend/scripts/schema.sql`):
- `users`: Basic user accounts (email, password_hash, display_name)
- `user_requests`: Query history (text, emojis, limit, Gemini analysis JSON)
- `recommended_songs`: Song results per request (Spotify metadata, position, why, matched_criteria JSON)

**Access**:
- `db.py`: Simple connection factory using `psycopg2` with `RealDictCursor`
- `db_queries.py`: User CRUD (`create_user()`, `get_user_by_email()`)
- `app.py`: Async saves via background `SAVE_QUEUE` worker thread to avoid blocking API responses

### Frontend Architecture

**Main UI** (`App.tsx`):
- Manages search state, loading states, analysis/song results
- Coordinates SearchInput, ResultsGrid, SongCard, EmojiPicker components
- Calls `/api/analyze` then `/api/recommend` for two-stage flow

**Components** (`src/components/`):
- `SearchInput.tsx`: Text query + emoji picker + popularity selector
- `ResultsGrid.tsx`: Grid layout for song cards
- `SongCard.tsx`: Individual song display with album art, preview, Spotify deep link
- `EmojiPicker.tsx`: Modal emoji selector (up to 12 emojis)
- `Modal.tsx`: Reusable modal wrapper
- `ui/`: shadcn/ui primitives (buttons, dialogs, inputs, etc.)

**API Client** (`src/services/api.ts`):
- Wrapper functions for `/api/search`, `/api/analyze`, `/api/recommend`, `/api/health`

## API Endpoints

- `POST /api/search`: One-shot search (analyze + recommend)
- `POST /api/analyze`: Mood analysis only
- `POST /api/recommend`: Recommend songs (auto-analyzes if analysis missing)
- `GET /api/health`: Service connectivity check
- `POST /api/users/register`: Create user account
- `POST /api/users/login`: Email/password login
- `GET /api/history/<user_id>`: Fetch user search history

## Testing & Scripts

- `backend/scripts/benchmark_gemini_models.py`: Benchmarking script for Gemini model performance
- `backend/scripts/init.sql`: Full database initialization with users table and password_hash column
- `backend/scripts/schema.sql`: Minimal schema (users, user_requests, recommended_songs tables)

## Recent Improvements

### P1.1 - Controller Refactor (Completed 2026-01-24)
- ✅ Extracted controllers from monolithic `app.py` (796 → 59 lines, 92.6% reduction)
- ✅ Implemented dependency injection for services
- ✅ Created Flask Blueprints for route organization
- ✅ Moved background worker to `workers/save_worker.py`
- ✅ All endpoints verified working, no breaking changes

See `.claude/P1.1-controller-refactor-summary.md` for details.

## Important Implementation Notes

1. **Gemini JSON Parsing**: Always use `response_format={"type": "json_object"}` to force JSON. If truncation occurs, `_salvage_to_last_complete_song()` trims to last valid object.

2. **Spotify Fuzzy Matching**: `spotify_service` runs multiple queries per song (exact track+artist, relaxed search, title-only fallback) and scores candidates by title similarity + primary artist match. Ignores featured artists in matching logic.

3. **Popularity Filtering**: Backend applies tolerance ranges and pads results if filter is too strict. Low popularity bands ("Growing", "Rising", "Under the Radar") use higher temperature (0.9 vs 0.8) in Gemini calls for variety.

4. **Async Database Saves**: `/api/recommend` queues saves to `SAVE_QUEUE` to avoid blocking response. Background worker (`_save_worker()`) persists requests and songs.

5. **Deduplication**: Uses `_song_identity()` to build stable keys (Spotify ID or title|artist) and `add_unique_songs()` to prevent duplicate results across multiple Gemini calls.

6. **Request Sizing**: Dynamic sizing uses `compute_first_request_size()` (1.5x limit, capped at 30) and `compute_second_request_size()` (2x remaining, capped at 40) to efficiently hit target counts after popularity filtering.

7. **Frontend State Management**: Two-stage flow shows analysis tags immediately after `/api/analyze`, then displays loading spinner while `/api/recommend` fetches songs. This provides fast user feedback.

8. **Configuration Management**: The app uses a two-layer config system:
   - **Environment variables** (`.env`): API keys, database URLs, debug flags
   - **JSON configs** (`backend/configs/`): All tunable parameters for request sizing, temperature, popularity ranges, etc.
   - Modify JSON configs to adjust behavior without code changes; use `ENVIRONMENT` env var to switch between dev/staging/prod presets

9. **Database Independence**: Core search/recommendation features work without PostgreSQL. Database features (user accounts, history, persistence) are optional and controlled by config flags (`database.save_queue.enabled`, `database.persistence.save_requests`, etc.).
