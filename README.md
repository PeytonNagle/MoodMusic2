# Mood to Music (Gemini + Spotify)

Full-stack app that turns mood descriptions (text + emojis) into Spotify-ready song picks. Gemini handles mood analysis and recommendations; Spotify enriches tracks with metadata and previews.

## Features
- Mood + emoji analysis with Gemini (OpenAI-compatible endpoint)
- AI song recommendations aligned to mood/criteria
- Spotify enrichment (art, preview URL, year, duration, deep link)
- Modern glassy UI with gradients; responsive layout
- Debug pane shows raw Gemini payloads

## Tech Stack
**Backend:** Flask, Google Gemini (via OpenAI client), Spotipy, python-dotenv  
**Frontend:** React, TypeScript, Vite, Tailwind CSS (prebuilt CSS), shadcn/ui, Lucide icons

## Project Structure
```
backend/
  app.py                 # Flask API (search/analyze/recommend/health)
  config.py              # Loads env vars (GEMINI + Spotify)
  services/
    gemini_service.py    # Mood analysis + recommendations (JSON forced)
    spotify_service.py   # Spotify search/enrichment with fuzzy matching
  requirements.txt
  .env.example           # (create your own .env)
frontend/
  package.json
  src/
    App.tsx              # Main UI + loading states
    components/          # SearchInput, ResultsGrid, SongCard, EmojiPicker, etc.
    services/api.ts      # Calls Flask API
```

## Environment Variables (`backend/.env`)
```
GEMINI_API_KEY=your_key_here            # required
SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret
DEBUG=true                              # optional
```

## Setup
### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Runs at `http://localhost:5000`.

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Vite dev server at `http://localhost:3000`.

## API
### POST /api/search
Body: `{"query": "upbeat indie rock for a road trip", "emojis": ["🚗"], "limit": 10}`  
Returns: `{ success, songs: [...], analysis, error }`

### POST /api/analyze
Body: `{"query": "...", "emojis": ["🙂"]}`  
Returns: `{ success, analysis, error }`

### POST /api/recommend
Body: `{"query": "...", "analysis": {...}, "limit": 10}` (auto-analyzes if analysis missing)  
Returns: `{ success, songs, analysis, error }`

### GET /api/health
Checks Gemini + Spotify connectivity.

## Notable Implementation Details
- Gemini responses use `response_format={"type": "json_object"}` to reduce parse errors.
- Spotify enrichment runs multiple queries and fuzzy ranking, focusing on primary artist (ignores `ft/feat`), and falls back gracefully when not found.
- Frontend shows analysis tags once (during analysis) and a visible spinner while recommendations are loading.

## Troubleshooting
- Missing keys: ensure `GEMINI_API_KEY`, `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET` are set.
- Parse errors: Gemini is forced to JSON; if issues persist, retry with a simpler prompt.
- No previews: some tracks lack `preview_url`; UI still lists them but cannot play a clip.

## Future Ideas
- Save/share playlists
- User auth + history
- More filters (energy, tempo, release year)
