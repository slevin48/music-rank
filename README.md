# 🎶 playd

A Tinder-like music ranking app. Pick winners in head-to-head track duels; ELO ratings surface your best tracks.

## Setup

### 1. Spotify app

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create an app — set the Redirect URI to `http://localhost:8000/callback`
3. Copy the Client ID and Client Secret

### 2. Configure

```bash
cp .env.example .env
# Edit .env and fill in your credentials
```

### 3. Install & run

```bash
uv pip install -r backend/requirements.txt
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Open [http://localhost:8000](http://localhost:8000).

## How it works

1. **Login** with Spotify OAuth
2. **Pick a playlist** or your **Liked Songs** — tracks are imported into SQLite
3. **Duel** — two tracks appear side-by-side; click the one you prefer
4. **Leaderboard** — tracks ranked by ELO score (starts at 1000, K=32)
5. **Export** — save your top N tracks as a new Spotify playlist

## Tech stack

- **Backend:** FastAPI + SQLite (Python)
- **Frontend:** Vanilla JS SPA (no build step)
- **Auth:** Spotify OAuth 2.0
- **PWA:** Service worker for offline support and mobile install
