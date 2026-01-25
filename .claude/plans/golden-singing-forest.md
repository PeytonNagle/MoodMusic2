# MoodMusic2: Prioritized Improvement Plan

## Executive Summary

This plan addresses three key improvement areas for the MoodMusic2 LLM application:
- **P1**: Code structure, modularity, and configuration management
- **P2**: Modern AI tooling for reliability, observability, and prompt management
- **P3**: Features including vector DB semantic search, caching, and enhanced music sources

Based on comprehensive codebase analysis, the current system has:
- 796-line monolithic `app.py` with business logic in Flask routes
- No LLM retry logic or observability
- No caching or connection pooling
- Opportunity for semantic search and multi-source music catalog

---

## P1 - CODE STRUCTURE & CONFIGURABILITY

### 1.1 Extract Controllers from Routes ⭐ Quick Win
**Complexity**: L (2-3 days)
**Dependencies**: None
**Implementation Order**: #1

**Current Issue**: `app.py` is 796 lines mixing HTTP handling, business logic, and database access

**Solution**: Create controller layer to separate concerns
```
backend/controllers/
├── search_controller.py     # Search, analyze, recommend logic
├── user_controller.py        # Auth endpoints
├── history_controller.py     # User history
```

**Changes**:
- Extract `generate_recommendations()` to `SearchController.generate_recommendations()`
- Extract `resolve_popularity_constraints()` to `SearchController`
- Routes become thin wrappers (5-10 lines)
- Inject services via constructor for testability

**Files**: `backend/app.py` → new `backend/controllers/`

**Impact**: Enables unit testing, improves maintainability, separates concerns

---

### 1.2 Add PostgreSQL Connection Pooling ⭐ Quick Win
**Complexity**: L (1-2 days)
**Dependencies**: None
**Implementation Order**: #2

**Current Issue**: Creates new DB connection per query (major performance bottleneck)

**Solution**: Use `psycopg2.pool.ThreadedConnectionPool`
```python
# db.py
_connection_pool = pool.ThreadedConnectionPool(
    minconn=2, maxconn=10,
    DATABASE_URL,
    cursor_factory=RealDictCursor
)
```

**Configuration** (`config.json`):
```json
"database": {
  "connection_pool": {
    "min_connections": 2,
    "max_connections": 10
  }
}
```

**Files**: `backend/db.py`, `backend/configs/config.json`

**Impact**: 10-50x performance improvement, better resource utilization

---

### 1.3 Centralize Error Handling
**Complexity**: L (2-3 days)
**Dependencies**: 1.1 (Controllers)
**Implementation Order**: #3

**Current Issue**: Error handling scattered across routes, inconsistent responses

**Solution**: Exception hierarchy + Flask error handlers
```
backend/exceptions/
├── base.py              # AppException
├── validation.py        # ValidationError (move existing)
├── service_errors.py    # GeminiError, SpotifyError
└── handlers.py          # Flask @errorhandler decorators
```

**Pattern**:
```python
class GeminiError(ServiceError):
    status_code = 503
    error_code = "GEMINI_ERROR"

@app.errorhandler(ServiceError)
def handle_service_error(e):
    return jsonify({'success': False, 'error': e.message, 'error_code': e.error_code}), e.status_code
```

**Files**: New `backend/exceptions/`, update `backend/app.py` and all services

**Impact**: Consistent error responses, better debugging, cleaner code

---

### 1.4 Add Config Schema Validation with Pydantic
**Complexity**: M (1 week)
**Dependencies**: None
**Implementation Order**: #4

**Current Issue**: JSON configs loaded without validation, silent failures on bad values

**Solution**: Pydantic models for config validation
```python
# config_schema.py
class GeminiConfig(BaseModel):
    model: str = "gemini-2.5-flash"
    temperatures: TemperatureConfig

class TemperatureConfig(BaseModel):
    analysis: float = Field(ge=0.0, le=2.0)
```

**Files**: New `backend/config_schema.py`, update `backend/config.py`

**Impact**: Catch config errors at startup, type safety, self-documenting

---

### 1.5 Add Structured Logging with Context
**Complexity**: L (2-3 days)
**Dependencies**: None
**Implementation Order**: #5

**Current Issue**: Basic logging, no request tracing, hard to debug

**Solution**: JSON structured logging with request context
```python
# utils/logging.py
class StructuredLogger:
    def info(self, message, **extra):
        context = request_context.get()  # user_id, request_id
        self.logger.info(json.dumps({
            'message': message,
            'level': 'info',
            **context,
            **extra
        }))
```

**Files**: New `backend/utils/logging.py`, update all log calls

**Impact**: Easy log filtering by request/user, better debugging, log aggregation ready

---

## P2 - MODERN AI TOOLING

### 2.1 Add Retry Logic with Exponential Backoff ⭐ Quick Win
**Complexity**: L (1-2 days)
**Dependencies**: None
**Implementation Order**: #1

**Current Issue**: No retry logic for Gemini API; single failure = user error

**Solution**: Use `tenacity` library
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(openai.RateLimitError)
)
def _call_gemini_with_retry(self, **kwargs):
    return self.client.chat.completions.create(**kwargs)
```

**Configuration** (`config.json`):
```json
"gemini": {
  "retry": {
    "max_attempts": 3,
    "min_wait_seconds": 1,
    "max_wait_seconds": 10
  }
}
```

**Files**: `backend/services/gemini_service.py`, `backend/requirements.txt`

**Impact**: 95%+ success rate on transient failures, better UX

---

### 2.2 Implement Prompt Management & Versioning
**Complexity**: M (1-2 weeks)
**Dependencies**: None
**Implementation Order**: #2

**Current Issue**: Prompts hardcoded in service; no versioning or A/B testing

**Solution**: Template-based prompt system with version tracking
```
backend/prompts/
├── templates/
│   ├── analyze_mood_v1.txt
│   ├── analyze_mood_v2.txt
│   ├── recommend_songs_v1.txt
└── prompt_manager.py
```

**Pattern**:
```python
class PromptManager:
    def render(self, template_name, version='latest', **kwargs):
        template = self._load_template(template_name, version)
        return {
            'prompt': template.render(**kwargs),
            'version': version
        }
```

**Database Migration**:
```sql
ALTER TABLE user_requests ADD COLUMN prompt_versions JSONB;
```

**Files**: New `backend/prompts/`, `backend/scripts/schema.sql`, update `gemini_service.py`

**Impact**: A/B testing, rollback capability, track prompt performance

---

### 2.3 Add Pydantic Models for LLM I/O Validation
**Complexity**: M (1 week)
**Dependencies**: None
**Implementation Order**: #3

**Current Issue**: Manual JSON parsing, fragile validation, salvage logic errors

**Solution**: Use `instructor` + Pydantic for structured outputs
```python
# models/llm_schemas.py
class MoodAnalysis(BaseModel):
    mood: str = Field(..., description="1-4 word mood")
    matched_criteria: List[str] = Field(default_factory=list)

class Song(BaseModel):
    title: str
    artist: str
    why: Optional[str] = None

# Usage with instructor
self.client = instructor.from_openai(openai_client)
response = self.client.chat.completions.create(
    response_model=AnalysisResponse,  # Pydantic model
    messages=[...]
)
```

**Files**: New `backend/models/llm_schemas.py`, update `backend/services/gemini_service.py`

**Impact**: Type-safe responses, better errors, remove salvage logic

---

### 2.4 Add LLM Observability with LangSmith
**Complexity**: M (1 week)
**Dependencies**: 2.2 (Prompt versioning helps)
**Implementation Order**: #4

**Current Issue**: No visibility into LLM performance, costs, or failures

**Solution**: Integrate LangSmith for tracing
```python
from langsmith.run_helpers import traceable

@traceable(run_type="llm", name="analyze_mood")
def analyze_mood(self, text, emojis):
    # Auto-logs inputs/outputs/latency/costs
```

**Configuration** (`config.json`):
```json
"observability": {
  "provider": "langsmith",
  "enabled": true,
  "sample_rate": 1.0
}
```

**Files**: `backend/services/gemini_service.py`, `backend/.env`

**Impact**: Debug failures, track costs, identify slow prompts, compare versions

---

### 2.5 Implement Prompt Caching ⭐ Quick Win
**Complexity**: L (2-3 days)
**Dependencies**: 2.2 (Prompt versioning)
**Implementation Order**: #5

**Current Issue**: Repeated queries re-analyze mood (waste tokens/latency)

**Solution**: Cache analysis results in Redis
```python
class AnalysisCache:
    def _cache_key(self, query, emojis, prompt_version):
        data = f"{query}|{sorted(emojis)}|{prompt_version}"
        return f"analysis:{hashlib.sha256(data.encode()).hexdigest()}"

    def get(self, query, emojis, prompt_version) -> Optional[dict]:
        # Check cache before Gemini call
```

**Files**: New `backend/services/cache_service.py`, update `gemini_service.py`

**Impact**: 50% reduction in Gemini calls, faster responses, lower costs

---

## P3 - FEATURES (VECTOR DB, SEARCH/RETRIEVAL)

### 3.1 Implement Semantic Search with pgvector
**Complexity**: H (2-3 weeks)
**Dependencies**: 1.2 (Connection pooling), 2.3 (Pydantic)
**Implementation Order**: #1

**Current Issue**: Can't find similar past searches, no semantic similarity

**Solution**: Add pgvector extension for semantic search
```sql
CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE user_requests
ADD COLUMN query_embedding vector(768);

CREATE INDEX ON user_requests
USING ivfflat (query_embedding vector_cosine_ops);
```

**Service**:
```python
class EmbeddingService:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def find_similar_requests(self, query, limit=10):
        embedding = self.embed_query(query)
        # Vector similarity search in PostgreSQL
```

**New Endpoint**: `POST /api/search/similar`

**Files**: New migration, new `backend/services/embedding_service.py`, update schema

**Impact**: Find similar searches, personalized recommendations, collaborative filtering

**Breakdown**: DB migration (1d), embedding service (2d), API (2d), backfill (2d), frontend (2d)

---

### 3.2 Add Redis Caching for Spotify Data ⭐ Quick Win
**Complexity**: M (1 week)
**Dependencies**: 3.1 (uses caching patterns)
**Implementation Order**: #2

**Current Issue**: Duplicate Spotify API calls for same tracks (100-300ms each)

**Solution**: Multi-layer cache (local + Redis)
```python
class SpotifyCache:
    def get_track(self, title, artist):
        key = f"track:{title}|{artist}"
        # L1: Local cache (instant)
        if key in self.local_cache:
            return self.local_cache[key]
        # L2: Redis (fast)
        cached = self.redis.get(key)
        if cached:
            return json.loads(cached)
```

**Configuration** (`config.json`):
```json
"cache": {
  "redis": {
    "host": "localhost",
    "ttl": {"spotify_track": 86400}
  }
}
```

**Files**: New `backend/services/spotify_cache.py`, update `spotify_service.py`

**Impact**: 80-90% cache hit rate, 100-300ms → <5ms, better rate limits

**Breakdown**: Redis setup (0.5d), cache service (1d), integration (1d), testing (1d)

---

### 3.3 Add Multi-Source Music Catalog (MusicBrainz)
**Complexity**: H (2 weeks)
**Dependencies**: 3.2 (Caching)
**Implementation Order**: #3

**Current Issue**: 10-20% of Gemini songs not found on Spotify

**Solution**: Fallback chain: Spotify → MusicBrainz → Last.fm
```python
class MusicSourceService:
    def enrich_song(self, title, artist):
        for source in [spotify, musicbrainz, lastfm]:
            try:
                track = source.search_track(title, artist)
                if track and self._is_valid_match(track):
                    track['source'] = source.name
                    return track
            except Exception as e:
                continue
```

**Files**: New `backend/services/music_source_service.py`, update `spotify_service.py`

**Impact**: 95%+ track coverage (vs 80-90%), better indie artist coverage

**Breakdown**: Abstraction (1d), MusicBrainz (2d), Last.fm (1d), fallback logic (1d), testing (2d)

---

### 3.4 Integrate Spotify Audio Features
**Complexity**: M (1 week)
**Dependencies**: 3.2 (Caching)
**Implementation Order**: #4

**Current Issue**: Can't match on musical attributes (energy, tempo, mood)

**Solution**: Use Spotify Audio Features API to score recommendations
```python
class AudioFeaturesService:
    def score_mood_match(self, track_features, mood_keywords):
        score = 0
        if 'energetic' in mood_keywords:
            score += track_features['energy'] * 50
            score += (track_features['tempo'] / 200) * 30
        if 'chill' in mood_keywords:
            score += (1 - track_features['energy']) * 50
```

**Configuration** (`config.json`):
```json
"spotify": {
  "audio_features": {
    "mood_mappings": {
      "energetic": {"energy": 0.7, "tempo": 120},
      "chill": {"energy": 0.3, "acousticness": 0.6}
    }
  }
}
```

**Files**: New `backend/services/audio_features_service.py`, update `spotify_service.py`

**Impact**: Better mood matching, verify Gemini suggestions, new filters

**Breakdown**: Integration (1d), mood mapping (2d), re-ranking (1d), testing (1d)

---

### 3.5 Build Playlist Creator & Sharing
**Complexity**: H (3 weeks)
**Dependencies**: 3.1 (Vector search), 1.2 (DB pooling)
**Implementation Order**: #5

**Current Issue**: Can't save or share recommendations, no Spotify integration

**Solution**: Playlist management with Spotify export
```sql
CREATE TABLE playlists (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    name TEXT,
    spotify_playlist_id TEXT,
    embedding vector(768)
);

CREATE TABLE playlist_songs (
    playlist_id INTEGER,
    spotify_track_id TEXT,
    position INTEGER
);
```

**API Endpoints**:
- `POST /api/playlists` - Create from search results
- `POST /api/playlists/:id/export/spotify` - Export to Spotify (OAuth)
- `POST /api/playlists/:id/share` - Generate share link
- `GET /api/playlists/shared/:code` - View shared playlist

**Files**: Migration, new `backend/services/playlist_service.py`, new frontend components

**Impact**: User engagement, social discovery, Spotify integration, viral growth

**Breakdown**: Schema (0.5d), service (2d), API (2d), Spotify OAuth (3d), frontend (3d), discovery (2d), testing (2d)

---

## Implementation Roadmap

### Phase 1: Foundation (2-3 weeks)
**Goal**: Stable, maintainable backend

**Week 1**:
- P1.1 Extract Controllers ⭐
- P1.2 Connection Pooling ⭐
- P1.3 Error Handling

**Week 2**:
- P1.5 Structured Logging
- P2.1 Retry Logic ⭐
- P2.5 Prompt Caching ⭐

**Week 3**:
- P1.4 Config Validation
- P2.3 Pydantic LLM Schemas

**Deliverable**: Testable, reliable backend with proper error handling

---

### Phase 2: AI Tooling (2-3 weeks)
**Goal**: Production-ready LLM integration

**Week 4-5**:
- P2.2 Prompt Management
- P2.4 LLM Observability

**Week 6**:
- Testing, documentation, refinement

**Deliverable**: Observable, versioned LLM system with prompt A/B testing

---

### Phase 3: Features (4-6 weeks)
**Goal**: User-facing enhancements

**Week 7-8**:
- P3.1 Semantic Search (pgvector)

**Week 9**:
- P3.2 Redis Caching ⭐
- P3.4 Audio Features

**Week 10-11**:
- P3.3 Multi-Source Catalog
- P3.5 Playlist Creator (start)

**Week 12**:
- P3.5 Playlist Creator (finish)
- Integration testing

**Deliverable**: Feature-rich platform with semantic search, caching, playlists

---

## Quick Wins (Start Here)

These 5 improvements provide maximum impact with minimal effort:

1. **P1.2 Connection Pooling** (1-2 days) → 10-50x database performance
2. **P2.1 Retry Logic** (1-2 days) → 95%+ LLM success rate
3. **P2.5 Prompt Caching** (2-3 days) → 50% fewer Gemini calls
4. **P1.1 Controllers** (2-3 days) → Testable, maintainable code
5. **P3.2 Spotify Caching** (1 week) → 80-90% faster track lookups

**Total Time**: ~2 weeks for 5 major improvements

---

## Success Metrics

### P1 - Code Quality
- Test coverage: 80%+ (from ~0%)
- Route handlers: <20 lines average
- DB connection time: <10ms
- Config validation: 100%

### P2 - AI Reliability
- LLM success rate: 98%+ (from ~90%)
- Prompt cache hit rate: 40-60%
- LLM latency: <1.5s average
- Prompt tracking: 100%

### P3 - Features
- Semantic search recall: 80%+
- Cache hit rate: 80-90%
- Track coverage: 95%+ (from 80-90%)
- User playlist adoption: Track metric

---

## Critical Files

### P1 - Code Structure
- `backend/app.py` - Extract to controllers
- `backend/db.py` - Add connection pooling
- `backend/config.py` - Pydantic validation
- `backend/services/requests_utils.py` - Error patterns

### P2 - AI Tooling
- `backend/services/gemini_service.py` - Retry, Pydantic, prompts
- `backend/configs/config.json` - LLM config
- New `backend/prompts/` - Template system

### P3 - Features
- `backend/scripts/schema.sql` - Vector extensions, playlists
- `backend/services/spotify_service.py` - Multi-source, audio features
- New `backend/services/embedding_service.py` - Semantic search

---

## Verification Plan

### After Phase 1
1. Run test suite: `pytest backend/tests/` (should pass)
2. Load test: 100 concurrent requests (no connection errors)
3. Check logs: Structured JSON format with request IDs
4. Config validation: Invalid config fails startup with clear error

### After Phase 2
1. Trigger rate limit: Verify retries work (check logs for attempts)
2. Change prompt version: Verify tracking in database
3. Review LangSmith dashboard: See traces for all requests
4. Cache hit rate: Should be 40%+ on repeated queries

### After Phase 3
1. Semantic search: Query returns similar past searches
2. Cache test: Popular song lookups <10ms
3. Multi-source: Gemini suggests indie track → found via MusicBrainz
4. Audio features: "energetic" query returns high-energy songs
5. Playlist: Create playlist → export to Spotify → verify in Spotify app

---

## Dependencies & Prerequisites

### Infrastructure
- PostgreSQL 15+ with pgvector extension
- Redis 6+ for caching
- Python 3.12 (current: 3.12)

### New Python Libraries
```txt
# Phase 1
psycopg2-binary (already installed)

# Phase 2
tenacity==8.2.3
instructor==1.0.0
pydantic==2.6.0
langsmith==0.1.0
jinja2==3.1.3

# Phase 3
sentence-transformers==2.3.0
musicbrainzngs==0.7.1
pylast==5.2.0
pgvector==0.2.4
redis==5.0.1
```

### Environment Variables
```env
# Existing
GEMINI_API_KEY=...
SPOTIPY_CLIENT_ID=...
SPOTIPY_CLIENT_SECRET=...
DATABASE_URL=...

# New for Phase 2
LANGSMITH_API_KEY=...

# New for Phase 3
REDIS_URL=redis://localhost:6379/0
```

---

## Risk Mitigation

### High Risk Areas
1. **pgvector migration** - Large database? Test on copy first
2. **Spotify OAuth** - Complex flow; start with basic export
3. **Breaking changes** - Use feature flags for gradual rollout

### Rollback Strategy
- Controllers: Can revert to monolithic app.py if issues
- Caching: Disable via config flag
- Vector search: Optional feature, doesn't break existing flow
- Prompts: Version tracking allows instant rollback

---

## Estimated Total Effort

- **Phase 1**: 2-3 weeks (foundation)
- **Phase 2**: 2-3 weeks (AI tooling)
- **Phase 3**: 4-6 weeks (features)

**Total**: 8-12 weeks for full implementation

**Quick Wins Only**: 2 weeks for 5 high-impact improvements
