import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "music_rank.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tracks (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                artist      TEXT NOT NULL,
                album       TEXT NOT NULL,
                image_url   TEXT,
                preview_url TEXT,
                playlist_id TEXT NOT NULL,
                elo         REAL NOT NULL DEFAULT 1000,
                wins        INTEGER NOT NULL DEFAULT 0,
                losses      INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS duels (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                winner_id   TEXT NOT NULL,
                loser_id    TEXT NOT NULL,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token       TEXT PRIMARY KEY,
                access_token  TEXT NOT NULL,
                refresh_token TEXT,
                expires_at    INTEGER NOT NULL
            );
        """)


def upsert_track(conn: sqlite3.Connection, track: dict):
    conn.execute("""
        INSERT INTO tracks (id, name, artist, album, image_url, preview_url, playlist_id)
        VALUES (:id, :name, :artist, :album, :image_url, :preview_url, :playlist_id)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            artist = excluded.artist,
            album = excluded.album,
            image_url = excluded.image_url,
            preview_url = excluded.preview_url,
            playlist_id = excluded.playlist_id
    """, track)


def get_tracks_for_playlist(conn: sqlite3.Connection, playlist_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM tracks WHERE playlist_id = ? ORDER BY elo DESC",
        (playlist_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_track(conn: sqlite3.Connection, track_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
    return dict(row) if row else None


def update_track_elo(conn: sqlite3.Connection, track_id: str, elo: float, won: bool):
    if won:
        conn.execute(
            "UPDATE tracks SET elo = ?, wins = wins + 1 WHERE id = ?",
            (elo, track_id)
        )
    else:
        conn.execute(
            "UPDATE tracks SET elo = ?, losses = losses + 1 WHERE id = ?",
            (elo, track_id)
        )


def record_duel(conn: sqlite3.Connection, winner_id: str, loser_id: str):
    conn.execute(
        "INSERT INTO duels (winner_id, loser_id) VALUES (?, ?)",
        (winner_id, loser_id)
    )


def get_duel_count(conn: sqlite3.Connection, playlist_id: str) -> int:
    row = conn.execute("""
        SELECT COUNT(*) as cnt FROM duels d
        JOIN tracks t ON t.id = d.winner_id
        WHERE t.playlist_id = ?
    """, (playlist_id,)).fetchone()
    return row["cnt"] if row else 0


def save_session(conn: sqlite3.Connection, token: str, access_token: str,
                 refresh_token: str | None, expires_at: int):
    conn.execute("""
        INSERT OR REPLACE INTO sessions (token, access_token, refresh_token, expires_at)
        VALUES (?, ?, ?, ?)
    """, (token, access_token, refresh_token, expires_at))


def get_session(conn: sqlite3.Connection, token: str) -> dict | None:
    row = conn.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()
    return dict(row) if row else None


def delete_session(conn: sqlite3.Connection, token: str):
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
