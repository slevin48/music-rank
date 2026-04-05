import os
import time
import random
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Cookie, HTTPException, Response, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from . import database as db
from . import spotify as sp
from .elo import update_elo

load_dotenv()

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
SESSION_COOKIE = "music_rank_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 1 week


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_session(session_token: str | None) -> dict:
    if not session_token:
        raise HTTPException(status_code=401, detail="Not logged in")
    with db.get_conn() as conn:
        sess = db.get_session(conn, session_token)
    if not sess:
        raise HTTPException(status_code=401, detail="Session expired")
    return sess


def _maybe_refresh(sess: dict) -> str:
    """Return a valid access token, refreshing if needed."""
    if sess["expires_at"] - time.time() < 60:
        data = sp.refresh_access_token(sess["refresh_token"])
        new_access = data["access_token"]
        new_expires = int(time.time()) + data["expires_in"]
        with db.get_conn() as conn:
            db.save_session(conn, sess["token"], new_access,
                            sess["refresh_token"], new_expires)
        return new_access
    return sess["access_token"]


def _pick_pair(tracks: list[dict]) -> tuple[dict, dict] | None:
    """Pick two tracks for a duel, slightly biased toward under-compared tracks."""
    if len(tracks) < 2:
        return None
    # Weight by fewest comparisons (wins+losses)
    weights = [1 / (t["wins"] + t["losses"] + 1) for t in tracks]
    total = sum(weights)
    probs = [w / total for w in weights]
    a, b = random.choices(tracks, weights=probs, k=2)
    while b["id"] == a["id"]:
        b = random.choices(tracks, weights=probs, k=1)[0]
    return a, b


# ── auth routes ───────────────────────────────────────────────────────────────

@app.get("/login")
def login(response: Response):
    state = secrets.token_urlsafe(16)
    url = sp.build_auth_url(state)
    resp = RedirectResponse(url)
    resp.set_cookie("oauth_state", state, max_age=300, httponly=True)
    return resp


@app.get("/callback")
def callback(code: str | None = None, state: str | None = None,
             error: str | None = None,
             oauth_state: str | None = Cookie(default=None)):
    if error:
        return RedirectResponse("/?error=" + error)
    if not code or state != oauth_state:
        return RedirectResponse("/?error=state_mismatch")

    token_data = sp.exchange_code(code)
    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")
    expires_at = int(time.time()) + token_data["expires_in"]

    session_token = secrets.token_urlsafe(32)
    with db.get_conn() as conn:
        db.save_session(conn, session_token, access_token, refresh_token, expires_at)

    resp = RedirectResponse("/")
    resp.set_cookie(SESSION_COOKIE, session_token, max_age=COOKIE_MAX_AGE,
                    httponly=True, samesite="lax")
    resp.delete_cookie("oauth_state")
    return resp


@app.post("/logout")
def logout(music_rank_session: str | None = Cookie(default=None)):
    resp = JSONResponse({"ok": True})
    if music_rank_session:
        with db.get_conn() as conn:
            db.delete_session(conn, music_rank_session)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@app.get("/api/me")
def get_me(music_rank_session: str | None = Cookie(default=None)):
    sess = _get_session(music_rank_session)
    access_token = _maybe_refresh(sess)
    user = sp.get_current_user(access_token)
    return {"id": user["id"], "display_name": user.get("display_name", user["id"]),
            "image": user["images"][0]["url"] if user.get("images") else None}


# ── playlist routes ───────────────────────────────────────────────────────────

@app.get("/api/playlists")
def get_playlists(music_rank_session: str | None = Cookie(default=None)):
    sess = _get_session(music_rank_session)
    access_token = _maybe_refresh(sess)
    return sp.get_user_playlists(access_token)


@app.post("/api/playlists/{playlist_id}/import")
def import_playlist(playlist_id: str,
                    music_rank_session: str | None = Cookie(default=None)):
    sess = _get_session(music_rank_session)
    access_token = _maybe_refresh(sess)
    tracks = sp.get_playlist_tracks(access_token, playlist_id)
    with db.get_conn() as conn:
        for track in tracks:
            db.upsert_track(conn, track)
    return {"imported": len(tracks)}


# ── duel routes ───────────────────────────────────────────────────────────────

@app.get("/api/playlists/{playlist_id}/duel")
def get_duel(playlist_id: str,
             music_rank_session: str | None = Cookie(default=None)):
    _get_session(music_rank_session)
    with db.get_conn() as conn:
        tracks = db.get_tracks_for_playlist(conn, playlist_id)
        duel_count = db.get_duel_count(conn, playlist_id)
    pair = _pick_pair(tracks)
    if not pair:
        raise HTTPException(status_code=404, detail="Not enough tracks")
    a, b = pair
    return {"track_a": a, "track_b": b, "duel_count": duel_count}


@app.post("/api/duel")
async def submit_duel(request: Request,
                      music_rank_session: str | None = Cookie(default=None)):
    _get_session(music_rank_session)
    body = await request.json()
    winner_id = body.get("winner_id")
    loser_id = body.get("loser_id")
    if not winner_id or not loser_id:
        raise HTTPException(status_code=400, detail="winner_id and loser_id required")

    with db.get_conn() as conn:
        winner = db.get_track(conn, winner_id)
        loser = db.get_track(conn, loser_id)
        if not winner or not loser:
            raise HTTPException(status_code=404, detail="Track not found")

        new_winner_elo, new_loser_elo = update_elo(winner["elo"], loser["elo"])
        db.update_track_elo(conn, winner_id, new_winner_elo, won=True)
        db.update_track_elo(conn, loser_id, new_loser_elo, won=False)
        db.record_duel(conn, winner_id, loser_id)

    return {
        "winner": {"id": winner_id, "elo": new_winner_elo},
        "loser": {"id": loser_id, "elo": new_loser_elo},
    }


@app.post("/api/duel/skip")
async def skip_duel(request: Request,
                    music_rank_session: str | None = Cookie(default=None)):
    _get_session(music_rank_session)
    # Just return OK — frontend will request a new pair
    return {"ok": True}


# ── leaderboard ───────────────────────────────────────────────────────────────

@app.get("/api/playlists/{playlist_id}/leaderboard")
def get_leaderboard(playlist_id: str,
                    music_rank_session: str | None = Cookie(default=None)):
    _get_session(music_rank_session)
    with db.get_conn() as conn:
        tracks = db.get_tracks_for_playlist(conn, playlist_id)
        duel_count = db.get_duel_count(conn, playlist_id)
    ranked = sorted(tracks, key=lambda t: t["elo"], reverse=True)
    for i, t in enumerate(ranked):
        t["rank"] = i + 1
    return {"tracks": ranked, "duel_count": duel_count}


# ── export ────────────────────────────────────────────────────────────────────

@app.post("/api/playlists/{playlist_id}/export")
async def export_playlist(playlist_id: str, request: Request,
                          music_rank_session: str | None = Cookie(default=None)):
    sess = _get_session(music_rank_session)
    access_token = _maybe_refresh(sess)
    body = await request.json()
    top_n = int(body.get("top_n", 20))
    name = body.get("name", "Music Rank Top Tracks")

    with db.get_conn() as conn:
        tracks = db.get_tracks_for_playlist(conn, playlist_id)

    top = sorted(tracks, key=lambda t: t["elo"], reverse=True)[:top_n]
    track_ids = [t["id"] for t in top]
    user = sp.get_current_user(access_token)
    new_playlist_id = sp.create_playlist(access_token, user["id"], name, track_ids)
    return {"playlist_id": new_playlist_id, "url": f"https://open.spotify.com/playlist/{new_playlist_id}"}


# ── serve SPA ─────────────────────────────────────────────────────────────────

@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    index = os.path.join(FRONTEND_DIR, "index.html")
    with open(index) as f:
        return HTMLResponse(f.read())
