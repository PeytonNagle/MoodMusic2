-- Schema for MoodMusic database

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE,
    display_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_requests (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    text_description TEXT,
    emojis JSONB,
    num_songs_requested INTEGER NOT NULL DEFAULT 10,
    gemini_analysis JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS recommended_songs (
    id SERIAL PRIMARY KEY,
    request_id INTEGER NOT NULL REFERENCES user_requests(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    position INTEGER NOT NULL,
    spotify_track_id TEXT,
    title TEXT NOT NULL,
    artist TEXT,
    album TEXT,
    album_art TEXT,
    preview_url TEXT,
    spotify_url TEXT,
    release_year TEXT,
    duration_ms INTEGER,
    duration_formatted TEXT,
    why_gemini_chose TEXT,
    matched_criteria JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_recommended_songs_request_position
    ON recommended_songs(request_id, position);

CREATE INDEX IF NOT EXISTS idx_recommended_songs_user_id
    ON recommended_songs(user_id);
