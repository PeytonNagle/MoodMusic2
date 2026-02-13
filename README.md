# MoodMusic2

Full-stack app that converts mood descriptions (text + emojis) into Spotify song recommendations using AI-powered mood analysis and smart Spotify enrichment.

## Features

- AI-powered mood analysis with song recommendations
- Spotify integration with fuzzy matching (album art, previews, metadata)
- 6-tier popularity filtering system with tolerance-based ranking
- User accounts with search history
- High-performance connection pooling (10-50x database performance improvement)
- Modern React + TypeScript UI with shadcn/ui components
- Controller-service architecture with dependency injection

## Tech Stack

**Backend:** Flask, PostgreSQL, AI (Gemini/Ollama), Spotipy, psycopg2 ThreadedConnectionPool
**Frontend:** React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui
**Architecture:** Controller-service pattern with dependency injection, Flask Blueprints, background worker queues

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
│   └── spotify_service.py     # Spotify API with fuzzy matching
├── workers/                    # Background tasks
│   └── save_worker.py         # Async database saves
├── configs/                    # JSON config files (dev/staging/prod)
└── db.py                       # Connection pool management
```

**Key Patterns:**
- **Controller-service architecture** with dependency injection (Jan 2026 refactor)
- **Flask Blueprints** for route organization by functional area
- **Provider abstraction pattern** for AI services (Gemini/Ollama)
- **ThreadedConnectionPool** with environment-specific sizing (dev: 1-5, prod: 5-20)
- **Async database saves** via background worker queue (non-blocking API responses)
- **Two-layer config:** JSON files + environment variable overrides

## Setup

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

# Database (optional - app works without it for core features)
DATABASE_URL=postgresql://user:pass@localhost:5432/moodmusic

# Environment
ENVIRONMENT=dev  # dev, staging, or prod (affects connection pool sizing)
DEBUG=true       # Enable Flask debug mode
```

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

**Popularity Tiers:** Global/Superstar (90-100), Hot/Established (75-89), Buzzing/Moderate (50-74), Growing (25-49), Rising (15-24), Under the Radar (0-14)

**Connection Pooling:** ThreadedConnectionPool with environment-specific sizing (dev: 1-5, prod: 5-20). Context manager pattern with graceful degradation.

**Spotify Matching:** Multi-query search with title similarity scoring, primary artist matching, and smart cleanup (ignores features/remasters).

## Configuration

JSON configs in `backend/configs/` (`config.json`, `config.{dev|staging|prod}.json`) with deep-merge and environment variable overrides.

Access via: `Config.get('path.to.value')`

See [CLAUDE.md](CLAUDE.md) for detailed configuration options.

## Troubleshooting

- **Missing API Keys:** Set `GEMINI_API_KEY` (if using Gemini), `SPOTIPY_CLIENT_ID`, and `SPOTIPY_CLIENT_SECRET` in `backend/.env`
- **Ollama Issues:** Ensure Ollama is running (`ollama serve`), model is pulled (`ollama list`), and `AI_PROVIDER=ollama` is set
- **Database Errors:** Verify `DATABASE_URL` format. App works without database for core features. Adjust pool settings in config files if needed.
- **Import Errors:** Activate virtual environment: `source ../.venv/bin/activate`
- **No Previews:** Some Spotify tracks lack preview URLs (API limitation)

