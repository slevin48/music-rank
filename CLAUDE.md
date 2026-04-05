# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
