# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

You are helping me build an application using the Spotify Web API. Follow these rules:

- OpenAPI spec: Refer to the Spotify OpenAPI specification at https://developer.spotify.com/reference/web-api/open-api-schema.yaml for all endpoint paths, parameters, and response schemas. Do not guess endpoints or field names.
- Authorization: Use the Authorization Code with PKCE flow (https://developer.spotify.com/documentation/web-api/tutorials/code-pkce-flow) for any user-specific data. If the app has a secure backend, the Authorization Code flow (https://developer.spotify.com/documentation/web-api/tutorials/code-flow) is also acceptable. Only use Client Credentials for public, non-user data. Never use the Implicit Grant flow (it is deprecated).
- Redirect URIs: Always use HTTPS redirect URIs (except http://127.0.0.1 for local development). Never use http://localhost or wildcard URIs. See https://developer.spotify.com/documentation/web-api/concepts/redirect_uri for requirements.
- Scopes: Request only the minimum scopes (https://developer.spotify.com/documentation/web-api/concepts/scopes) needed for the features being built. Do not request broad scopes preemptively.
- Token management: Store tokens securely. Never expose the Client Secret in client-side code. Implement token refresh (https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens) logic and send the user through authorization again when a refresh token expires.
- Rate limits: Implement exponential backoff and respect the Retry-After header when receiving HTTP 429 responses. Do not retry immediately or in tight loops.
- Deprecated endpoints: Do not use deprecated endpoints. Prefer /playlists/{id}/items over /playlists/{id}/tracks, and use /me/library over the type-specific library endpoints.
- Error handling: Handle all HTTP error codes documented in the OpenAPI schema. Read the returned error message and use it to provide meaningful feedback to the user.
- Developer Terms of Service: Comply with the Spotify Developer Terms (https://developer.spotify.com/terms). In particular: do not cache Spotify content beyond what is needed for immediate use, always attribute content to Spotify, and do not use the API to train machine learning models on Spotify data.


## Commands

```bash
# Install dependencies
uv pip install -r backend/requirements.txt

# Run dev server (from project root)
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# No test suite configured yet
```

## Architecture

**playd** — a Spotify music ranking app. Users import playlists, rank tracks via head-to-head ELO duels, and export top tracks back to Spotify.

### Backend (FastAPI + SQLite)

- `backend/main.py` — All routes, session management, CORS middleware. Frontend is mounted as static files at `/static`. Cookie-based auth (`music_rank_session` httponly cookie).
- `backend/spotify.py` — Spotify OAuth 2.0 flow and API calls via httpx. Scopes include `user-library-read` for Liked Songs. `show_dialog` controls whether Spotify re-prompts consent.
- `backend/database.py` — Raw sqlite3 (not SQLAlchemy ORM despite it being in requirements). Three tables: `tracks` (with ELO/wins/losses), `duels`, `sessions`. Auto-inits on app startup.
- `backend/elo.py` — Standard chess ELO formula (K=32, start=1000).

### Frontend (Vanilla JS SPA)

- `frontend/index.html` + `frontend/app.js` + `frontend/style.css` — No build step, no framework. Five screens managed by toggling CSS classes. Single `state` object.
- `frontend/sw.js` — Service worker for PWA/offline support. Cache versioned via `CACHE_NAME`.

### Key patterns

- Auth flow: `/login` → Spotify OAuth → `/callback` → session cookie → `_maybe_refresh()` auto-refreshes tokens <60s before expiry.
- Liked Songs use special playlist ID `__liked__` and fetch from `/me/tracks` (capped at 500).
- Duel pair selection is weighted toward tracks with fewer comparisons: `weight = 1 / (wins + losses + 1)`.
- Spotify API calls are paginated manually (limit 50-100 per request).

## Environment

Requires `.env` (see `.env.example`):
- `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` — from Spotify Developer Dashboard
- `REDIRECT_URI` — must match dashboard setting (localhost for dev, production URL for deploy)
- `DATABASE_URL` — optional, defaults to `backend/music_rank.db`

## Deployment

Hosted on Render.com with Cloudflare CDN in front. Static assets have no cache-busting — CSS/JS changes may require Cloudflare cache purge.
