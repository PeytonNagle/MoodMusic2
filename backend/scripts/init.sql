-- =========================================================
-- OPTIONAL: wipe existing tables (for test environments)
-- Comment these out if you don't want to drop data
-- =========================================================
DROP TABLE IF EXISTS recommended_songs;
DROP TABLE IF EXISTS user_requests;
DROP TABLE IF EXISTS users;

-- =========================================================
-- users: basic user login/account table
-- =========================================================
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    email           TEXT UNIQUE,              -- make NOT NULL if you require email
    password_hash   TEXT,                    -- store password hashes, not plain text
    display_name    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Optional index to speed up login lookup by email
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);


-- =========================================================
-- user_requests: one row per “mood” request from the user
-- =========================================================
CREATE TABLE user_requests (
    id                   SERIAL PRIMARY KEY,
    user_id              INTEGER REFERENCES users(id) ON DELETE SET NULL,
    
    -- What the user typed / sent
    text_description     TEXT NOT NULL,
    emojis               JSONB,              -- e.g. ["😴","📚"]
    num_songs_requested  INTEGER NOT NULL,   -- usually 10

    -- Optional slider parameters / constraints
    energy_target        NUMERIC(3,2),       -- 0.00–1.00
    tempo_min            INTEGER,
    tempo_max            INTEGER,
    valence_target       NUMERIC(3,2),       -- 0.00–1.00 “happiness”

    -- Gemini’s analysis blob (whatever structure you return)
    -- e.g. {"mood": "tired, relaxed", "matched_criteria": ["genre: lofi","activity: studying"]}
    gemini_analysis      JSONB,

    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_user_requests_user_id
    ON user_requests (user_id);

CREATE INDEX IF NOT EXISTS idx_user_requests_created_at
    ON user_requests (created_at);


-- =========================================================
-- recommended_songs: songs returned for each request
-- =========================================================
CREATE TABLE recommended_songs (
    id                   SERIAL PRIMARY KEY,
    request_id           INTEGER NOT NULL REFERENCES user_requests(id) ON DELETE CASCADE,

    -- Order in the list (1..N)
    position             INTEGER NOT NULL,

    -- Core song identity
    spotify_track_id     TEXT,               -- Spotify ID (can be null if not found)
    title                TEXT NOT NULL,
    artist               TEXT NOT NULL,
    album                TEXT,
    album_art            TEXT,               -- URL
    preview_url          TEXT,
    spotify_url          TEXT,
    release_year         TEXT,               -- keep as TEXT because Spotify dates can be YYYY or YYYY-MM-DD

    -- Duration details
    duration_ms          INTEGER,
    duration_formatted   TEXT,               -- "3:45"

    -- Extra AI explanation
    why_gemini_chose               TEXT,               -- super short “why this song”
    matched_criteria         JSONB,              -- e.g. ["mood: tired", "genre: lofi"]

    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index to quickly get all songs for a request in order
CREATE INDEX IF NOT EXISTS idx_recommended_songs_request_id_position
    ON recommended_songs (request_id, position);
