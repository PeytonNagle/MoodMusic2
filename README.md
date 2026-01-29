# MoodMusic2

Full-stack app that converts mood descriptions (text + emojis) into Spotify song recommendations using Google Gemini AI.

## Features

- AI-powered mood analysis with Google Gemini
- Smart song recommendations with explanations
- Spotify integration (album art, previews, metadata)
- 6-tier popularity filtering system
- User accounts with search history
- Connection pooling for 10-50x database performance
- Modern React + TypeScript UI

## Tech Stack

**Backend:** Flask, PostgreSQL, Google Gemini AI, Spotipy, psycopg2 ThreadedConnectionPool
**Frontend:** React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui

## Architecture

```
backend/
├── app.py                      # Flask initialization (59 lines)
├── controllers/                # Business logic (search, users, history)
├── services/                   # External APIs (Gemini, Spotify)
├── workers/                    # Background database saves
├── configs/                    # JSON config files (dev/staging/prod)
└── db.py                       # Connection pool management
```

**Key Patterns:**
- Controller-service architecture with dependency injection
- ThreadedConnectionPool with environment-specific sizing (dev: 1-5, prod: 5-20)
- Async database saves via background worker queue
- Two-layer config: JSON files + environment variables

## Setup

### Environment Variables

Create `backend/.env`:

```bash
# Required
GEMINI_API_KEY=your_gemini_api_key
SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret

# Optional
DATABASE_URL=postgresql://user:pass@localhost:5432/moodmusic
ENVIRONMENT=dev  # dev, staging, or prod
```

### Installation

```bash
# Backend
cd backend
python -m venv ../.venv
source ../.venv/bin/activate
pip install -r requirements.txt

# Database (optional - app works without it)
psql $DATABASE_URL -f backend/scripts/schema.sql

# Frontend
cd frontend
npm install
```

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
1. Parse & validate request
2. Gemini analyzes mood from text + emojis
3. Gemini generates song recommendations
4. Spotify enriches with metadata via fuzzy matching
5. Apply popularity filtering with tolerance
6. Background worker saves to PostgreSQL (non-blocking)

**Multi-Attempt Strategy:**
Makes up to 2 Gemini requests with dynamic sizing (1.5x → 2x remaining) to hit target count after popularity filtering.

**Popularity System:**
6 tiers from Global/Superstar (90-100) to Under the Radar (0-14) with tolerance-based filtering.

**Connection Pooling:**
Lazy-initialized ThreadedConnectionPool with graceful degradation when database unavailable. Context manager pattern: `with get_db_connection() as conn:`

**Spotify Fuzzy Matching:**
Multi-query search with title similarity scoring, primary artist matching, and smart cleanup (ignores features/remasters).

## Configuration

JSON configs in `backend/configs/` with environment overrides:

- `config.json` - Base defaults
- `config.dev.json` - Development overrides
- `config.prod.json` - Production overrides

Access via: `Config.get('database.connection_pool.min_connections')`

## Troubleshooting

**Missing API Keys:** Set `GEMINI_API_KEY`, `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET` in `backend/.env`

**Database Errors:** Check `DATABASE_URL` format. App works without database for core search features.

**No Previews:** Some Spotify tracks lack preview URLs.

**Pool Issues:** Adjust `min_connections`/`max_connections` in config files per environment.

