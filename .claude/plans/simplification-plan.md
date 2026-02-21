# Codebase Simplification & Readability Plan

## Context
Full backend audit for complexity, duplication, and inconsistent patterns. No functional changes — this is a readability and maintainability pass. Goal is to reduce cognitive load, eliminate duplicate code, and unify inconsistent conventions without altering any existing behavior.

---

## Action Plan (Prioritized by Impact)

### HIGH IMPACT — Clear wins, no behavior risk

**1. `services/gemini_service.py` + `services/ollama_service.py` → `services/base_mood_service.py`**
— Extract `_extract_json()`, `_extract_json_with_salvage()`, and `_salvage_to_last_complete_song()` into `BaseMoodService` as protected methods. Both services contain ~100 lines of near-identical logic. Subclasses override only where behavior genuinely differs.
— **Impact:** ~100 lines eliminated. Both service files shrink significantly. Zero behavior change.

**2. `db_queries.py` + `workers/save_worker.py` — Standardize JSON serialization**
— Currently split: `db_queries.py` uses `json.dumps()`, `save_worker.py` uses `psycopg2.extras.Json()`. Pick one (`psycopg2.extras.Json` is correct for psycopg2) and apply consistently.
— **Impact:** Eliminates a latent bug vector. Low risk, single-pass change.
— ⚠️ **Flag:** Test database writes after change — different serialization could affect stored format for existing rows.

**3. `db_queries.py` + `workers/save_worker.py` — Extract repeated DB connection boilerplate**
— The `with get_db_connection() as conn: / if conn is None: / logger.warning(...)` pattern appears 5+ times. Extract to a small helper (decorator or context manager wrapper) in `db.py`.
— **Impact:** Every DB function becomes shorter and more readable. Zero behavior change.

**4. `controllers/search_controller.py` — Extract service availability checks**
— `if not self.mood_service` and `if not self.spotify_service` blocks are copy-pasted into `search_music()`, `analyze()`, and `recommend()`. Extract to a single `_require_services()` method that returns an error response tuple or None.
— **Impact:** ~15 lines × 3 occurrences collapsed to one call. Centralizes the error message.

**5. `config.py` — Remove 8 redundant convenience methods**
— `max_emojis()`, `default_song_limit()`, `min_song_limit()`, `max_song_limit()`, `save_queue_enabled()`, `save_requests_enabled()`, `save_songs_enabled()`, `save_queue_max_size()`, `save_queue_behavior()` all wrap `Config.get()` with a hardcoded path. Remove them and update call sites to use `Config.get()` directly.
— **Impact:** Shrinks Config API surface; forces callers to be explicit about what they're reading.
— ⚠️ **Flag:** Requires grep for all call sites (primarily `requests_utils.py`, `workers/save_worker.py`, `app.py`). Breaking if any call site is missed.

---

### MEDIUM IMPACT — Readability wins, requires care

**6. `controllers/search_controller.py` — Break up `generate_recommendations()` (74 lines)**
— Currently does: request sizing, AI call, Spotify enrichment, popularity filtering, deduplication, and padding fallback — all in one method. Split into focused private methods:
  - `_fetch_and_enrich(num_songs, ...)` → single AI + Spotify round trip
  - `_pad_with_unfiltered(filtered, all_enriched, limit)` → fallback padding logic
— **Impact:** Major readability improvement. Each unit is testable in isolation.

**7. `controllers/search_controller.py` — Fix unreachable code in `resolve_popularity_constraints()`**
— An `elif label_clean.lower() == "any"` branch (~line 88) can never be reached because the same condition is already handled higher in the chain. Remove the dead branch and flatten the if/elif chain.
— **Impact:** ~20 lines simplified; eliminates confusing dead code. Low risk.

**8. `app.py` — Consolidate triple cleanup logic**
— Cleanup (`save_worker.stop()`, `db.close_pool()`) is triggered from three places: `teardown_appcontext`, `signal_handler`, and a `finally` block in `__main__`. Extract a single `_cleanup()` function called from all three.
— **Impact:** Future changes to shutdown logic happen in one place.

**9. `config.py` — Add `Config.get_section(key)` public API**
— `app.py` accesses `Config._config_data` directly (private attribute) to pass raw sections to services. Add a `Config.get_section(key)` classmethod as the proper public interface, then update `app.py` to use it.
— **Impact:** Fixes encapsulation violation. No behavior change.

**10. `controllers/search_controller.py` — Unify error handling in endpoint methods**
— `search_music()`, `analyze()`, `recommend()` each have identical `except ValidationError / except Exception` blocks with slightly different response shapes. Extract a `_error_response(exc, empty_fields)` helper on `BaseController`.
— **Impact:** ~30 lines reduced; enforces consistent error response structure across all endpoints.

---

### LOWER IMPACT — Polish and hygiene

**11. `controllers/user_controller.py` — Use `require_json_body()` from `requests_utils`**
— Both `register_user()` and `login_user()` manually check `request.is_json`. The utility `require_json_body()` already does this.
— **Impact:** 4 lines removed; uses established validation layer. No behavior change.

**12. `workers/save_worker.py` — Convert static methods to module-level functions**
— `_save_user_request()` and `_save_recommended_song()` are `@staticmethod` but called as `self._save_*()`. They don't use instance state. Move to module-level private functions.
— **Impact:** Removes anti-pattern; no behavior change.

**13. `db.py` — Replace deprecated `get_connection()` with a logged warning**
— The function is deprecated but silent. Add a `logger.warning("get_connection() is deprecated...")` call so it surfaces in logs.
— **Impact:** Makes technical debt visible. No behavior change.

**14. `config.py` + `db.py` — Replace `print()` with `logger`**
— `validate_config()` in `config.py` and `test_connection()` in `db.py` use `print()` while everything else uses the `logging` module.
— **Impact:** Log output goes through the unified logging system. No behavior change.

**15. `blueprints.py` — Reduce blueprint factory boilerplate**
— Five `create_*_blueprint()` functions share the same 4-line pattern. Consolidate into a single `_make_blueprint()` helper or fold inline into `register_blueprints()`.
— **Impact:** Minor reduction in boilerplate in a low-traffic file.

---

## Files Touched

| File | Actions |
|------|---------|
| `services/base_mood_service.py` | Add shared JSON helpers (#1) |
| `services/gemini_service.py` | Remove duplicated JSON helpers, call base (#1) |
| `services/ollama_service.py` | Remove duplicated JSON helpers, call base (#1) |
| `db_queries.py` | Standardize JSON serialization (#2), extract DB boilerplate (#3) |
| `workers/save_worker.py` | Standardize JSON serialization (#2), extract DB boilerplate (#3), demote static methods (#12) |
| `db.py` | Add DB boilerplate helper (#3), deprecation warning (#13), print→logger (#14) |
| `controllers/search_controller.py` | Extract service check (#4), split generate_recommendations (#6), fix dead code (#7), unify error handling (#10) |
| `config.py` | Remove convenience methods (#5), add get_section() (#9), print→logger (#14) |
| `app.py` | Consolidate cleanup (#8), use Config.get_section() (#9) |
| `controllers/user_controller.py` | Use require_json_body() (#11) |
| `controllers/base_controller.py` | Add _error_response() helper (#10) |
| `blueprints.py` | Reduce boilerplate (#15) |
| `services/requests_utils.py` | Update Config call sites if convenience methods removed (#5) |

---

## Verification

- `python app.py` — server starts, no import errors
- `GET /api/health` — returns `{ status: ok, services: { ai_service: true, spotify: true } }`
- `POST /api/recommend` with a mood query — returns songs with Spotify metadata
- Popularity filtering works across label changes (`"Growing"`, `"Global / Superstar"`)
- Database writes persist correctly (`user_requests` + `recommended_songs`)
- No `print()` output in logs — all output goes through logger
