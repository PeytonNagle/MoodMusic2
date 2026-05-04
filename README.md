# MoodMusic2

Full-stack app that converts mood descriptions (text + emojis) into song recommendations using AI-powered mood analysis with pluggable music providers (iTunes by default, Spotify optional).

Try it here!: https://moodtomusic.up.railway.app/

## Features

- AI-powered mood analysis with song recommendations (Gemini or Ollama)
- Pluggable music providers — iTunes Search API (default, no auth) or Spotify
- Fuzzy matching with album art, 30s previews, and metadata
- 6-tier popularity filtering with tolerance-based ranking (Spotify only; iTunes bypasses)
- Optional user accounts with search history
- ThreadedConnectionPool for PostgreSQL with env-specific sizing
- React + TypeScript UI with shadcn/ui

## Tech Stack

**Backend:** Flask, PostgreSQL, AI (Gemini/Ollama), Spotipy / iTunes Search API, psycopg2 ThreadedConnectionPool
**Frontend:** React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui
**Architecture:** Controller-service pattern with DI, Flask Blueprints, provider abstractions, background worker queues

## Architecture

```
backend/
├── app.py                      # Flask initialization (59 lines, 92.6% reduction from 796)
├── blueprints.py               # Route definitions with controller injection
├── controllers/                # Business logic layer
│   ├── search_controller.py   # Search, analyze, recommend endpoints
│   ├── user_controller.py     # Registration, authentication
│   ├── history_controller.py  # User search history
│   └── health_controller.py   # Health checks
├── services/                   # External API integrations
│   ├── base_mood_service.py   # Abstract AI provider interface
│   ├── gemini_service.py      # Gemini implementation
│   ├── ollama_service.py      # Ollama implementation
│   ├── service_factory.py     # AI provider factory
│   ├── base_music_service.py  # Abstract music provider interface
│   ├── itunes_service.py      # iTunes Search API (default, no auth)
│   ├── spotify_service.py     # Spotify API with fuzzy matching
│   └── music_service_factory.py # Music provider factory
├── workers/                    # Background tasks
│   └── save_worker.py         # Async database saves
├── configs/                    # JSON config files (dev/staging/prod)
└── db.py                       # Connection pool management
```

**Key Patterns:**
- **Controller-service architecture** with dependency injection
- **Flask Blueprints** for route organization
- **Provider abstractions** for both AI (Gemini/Ollama) and music (iTunes/Spotify), selectable via env or JSON config
- **ThreadedConnectionPool** with environment-specific sizing (dev: 1-5, prod: 5-20)
- **Async database saves** via background worker queue
- **Two-layer config:** JSON files + environment variable overrides

## Setup

### Environment Variables

Create `backend/.env`:

```bash
# AI Provider
AI_PROVIDER=gemini  # or 'ollama' for local inference
GEMINI_API_KEY=your_gemini_api_key  # required if using Gemini
OLLAMA_BASE_URL=http://localhost:11434  # optional, override for remote Ollama

# Music Provider (defaults to 'itunes' — no credentials needed)
MUSIC_PROVIDER=itunes  # or 'spotify'

# Spotify (only required if MUSIC_PROVIDER=spotify)
SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret

# Database (optional - app works without it for core features)
DATABASE_URL=postgresql://user:pass@localhost:5432/moodmusic

# Environment
ENVIRONMENT=dev  # dev, staging, or prod (affects connection pool sizing)
DEBUG=true       # Enable Flask debug mode

# Required for any non-dev deployment (used to sign JWTs)
SECRET_KEY=replace-with-32+-bytes-of-random  # required when ENVIRONMENT != dev

# Comma-separated allowlist of frontend origins. Required for public deploys.
CORS_ALLOWED_ORIGINS=https://your-frontend.up.railway.app
```

### Public / Demo Deployment Notes

For a publicly-linked deploy (e.g., Railway):

- Set `ENVIRONMENT=prod` and a strong random `SECRET_KEY` (the app refuses to start without it outside dev).
- Set `CORS_ALLOWED_ORIGINS` to your frontend URL(s); the API rejects every other origin.
- Per-IP rate limits are applied automatically (Flask-Limiter, in-memory): 10/min on `/api/search` and `/api/recommend`, 20/min on `/api/analyze`, 5/min on `/api/users/register|login`. To run multiple backend instances, swap to a Redis storage backend (`Limiter(..., storage_uri="redis://...")` in `app.py`).
- `/api/history/<user_id>` requires a `Authorization: Bearer <token>` header and the token's `sub` must match the path `user_id`. Tokens are issued by `/api/users/login` and `/api/users/register`.

### Installation

```bash
# Backend
cd backend
python -m venv ../.venv
source ../.venv/bin/activate
pip install -r requirements.txt

# Database (optional - app works without it for core features)
psql $DATABASE_URL -f backend/scripts/schema.sql

# Frontend
cd frontend
npm install
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

### Run

```bash
# Backend (http://localhost:5000)
cd backend && source ../.venv/bin/activate && python app.py

# Frontend (http://localhost:3000)
cd frontend && npm run dev
```

## API Endpoints

**POST /api/search** - One-shot search (analyze + recommend)
```json
{"query": "upbeat indie rock", "emojis": ["🚗"], "limit": 10}
```

**POST /api/analyze** - Mood analysis only
**POST /api/recommend** - Get recommendations
**POST /api/users/register** - Create account
**POST /api/users/login** - Authenticate
**GET /api/history/:user_id** - Search history
**GET /api/health** - Service health check

## Key Implementation Details

**Request Flow:**
1. Validate request → 2. AI mood analysis → 3. Generate recommendations → 4. Spotify enrichment → 5. Apply popularity filters → 6. Queue async database save

**Multi-Attempt Strategy:** Makes up to 2 AI requests with dynamic sizing (1.5x → 2x) to hit target count after filtering.

**Popularity Tiers (Spotify):** Global/Superstar (90-100), Hot/Established (75-89), Buzzing/Moderate (50-74), Growing (25-49), Rising (15-24), Under the Radar (0-14). iTunes does not expose a popularity score, so the filter is bypassed when iTunes is active.

**Connection Pooling:** ThreadedConnectionPool with environment-specific sizing (dev: 1-5, prod: 5-20). Context manager pattern with graceful degradation.

**Track Matching:** Multi-query search with title similarity scoring, primary artist matching, and smart cleanup (ignores features/remasters). Both providers normalize to a shared `track_id` / `track_url` / `preview_url` payload shape.

## Configuration

JSON configs in `backend/configs/` (`config.json`, `config.{dev|staging|prod}.json`) with deep-merge and environment variable overrides.

Access via: `Config.get('path.to.value')`

See [CLAUDE.md](CLAUDE.md) for detailed configuration options.

## Troubleshooting

- **Missing API Keys:** Set `GEMINI_API_KEY` (if using Gemini). Spotify credentials are only required when `MUSIC_PROVIDER=spotify`.
- **Ollama Issues:** Ensure Ollama is running (`ollama serve`), model is pulled (`ollama list`), and `AI_PROVIDER=ollama` is set.
- **Database Errors:** Verify `DATABASE_URL` format. App works without a database for core features.
- **Import Errors:** Activate virtual environment: `source ../.venv/bin/activate`.
- **No Previews:** Some Spotify tracks lack preview URLs (API limitation). iTunes returns previews for nearly all tracks.

