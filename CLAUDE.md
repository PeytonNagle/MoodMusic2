# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MoodMusic2 is a full-stack application that converts mood descriptions (text + emojis) into Spotify song recommendations using Google Gemini AI for analysis and the Spotify API for enrichment.

**Stack:**
- Backend: Flask + PostgreSQL, Google Gemini (via OpenAI-compatible endpoint), Spotipy
- Frontend: React + TypeScript, Vite, Tailwind CSS, shadcn/ui components

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

### Database Setup
```bash
# Initialize database schema (PostgreSQL)
psql $DATABASE_URL -f backend/scripts/schema.sql
```

## Environment Configuration

Create `backend/.env` with:
```
GEMINI_API_KEY=your_key_here
SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret
DATABASE_URL=postgresql://user:pass@host:port/dbname
DEBUG=true  # optional
```

## Architecture & Key Patterns

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

## Important Implementation Notes

1. **Gemini JSON Parsing**: Always use `response_format={"type": "json_object"}` to force JSON. If truncation occurs, `_salvage_to_last_complete_song()` trims to last valid object.

2. **Spotify Fuzzy Matching**: `spotify_service` runs multiple queries per song (exact track+artist, relaxed search, title-only fallback) and scores candidates by title similarity + primary artist match. Ignores featured artists in matching logic.

3. **Popularity Filtering**: Backend applies tolerance ranges and pads results if filter is too strict. Low popularity bands ("Growing", "Rising", "Under the Radar") use higher temperature (0.9 vs 0.8) in Gemini calls for variety.

4. **Async Database Saves**: `/api/recommend` queues saves to `SAVE_QUEUE` to avoid blocking response. Background worker (`_save_worker()`) persists requests and songs.

5. **Deduplication**: Uses `_song_identity()` to build stable keys (Spotify ID or title|artist) and `add_unique_songs()` to prevent duplicate results across multiple Gemini calls.

6. **Request Sizing**: Dynamic sizing uses `compute_first_request_size()` (1.5x limit, capped at 30) and `compute_second_request_size()` (2x remaining, capped at 40) to efficiently hit target counts after popularity filtering.

7. **Frontend State Management**: Two-stage flow shows analysis tags immediately after `/api/analyze`, then displays loading spinner while `/api/recommend` fetches songs. This provides fast user feedback.
