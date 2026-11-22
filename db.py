"""SQLite storage: one row per guest ("session") with a secret token and download tracking.

Each call opens a short-lived connection, so it's safe to use from the watcher thread, the web
server and the GUI at the same time (WAL mode lets readers and a writer work together).
"""
from __future__ import annotations

import os
import secrets
import sqlite3
import threading
import time
from pathlib import Path

from config import data_dir

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id                INTEGER PRIMARY KEY,
    token             TEXT NOT NULL UNIQUE,          -- secret part of the QR link: /s/<token>
    folder            TEXT NOT NULL,                 -- normalised photos folder
    guest_key         TEXT NOT NULL,                 -- grouping key from naming.guest_key()
    name              TEXT NOT NULL,                 -- display name, e.g. "Omnya & Fatma"
    photo_count       INTEGER NOT NULL DEFAULT 0,
    status            TEXT NOT NULL DEFAULT 'collecting',   -- collecting | ready
    photos_after_send INTEGER NOT NULL DEFAULT 0,    -- 1 = photos arrived after the guest downloaded
    created_at        REAL NOT NULL,
    updated_at        REAL NOT NULL,                 -- last time the photo set changed
    ready_at          REAL,
    UNIQUE (folder, guest_key)
);
CREATE INDEX IF NOT EXISTS idx_sessions_folder ON sessions(folder, created_at);
"""

STATUS_COLLECTING = "collecting"
STATUS_READY = "ready"


def normalise_folder(folder: str | Path) -> str:
    return os.path.normcase(os.path.abspath(str(folder)))


def new_token() -> str:
    # 8 random bytes -> 11 URL-safe characters: impossible to guess, short enough for a QR code.
    return secrets.token_urlsafe(8)


class Database:
    def __init__(self, path: str | Path | None = None):
        self.path = str(path or data_dir() / "photobooth.db")
        self._write_lock = threading.Lock()
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)
            # Upgrades for databases created by earlier versions.
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(sessions)")}
            for column, kind in (("opened_at", "REAL"), ("downloaded_at", "REAL"),
                                 ("downloads", "INTEGER NOT NULL DEFAULT 0")):
                if column not in columns:
                    conn.execute(f"ALTER TABLE sessions ADD COLUMN {column} {kind}")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ------------------------------------------------------------ sessions
    def upsert_guest(self, folder: str, key: str, name: str, photo_count: int,
                     now: float | None = None) -> tuple[dict, bool]:
        """Create or update a guest. Returns (session, changed)."""
        now = now or time.time()
        folder = normalise_folder(folder)
        with self._write_lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE folder=? AND guest_key=?", (folder, key)).fetchone()
            if row is None:
                for _ in range(5):  # token collisions are astronomically unlikely, but be safe
                    try:
                        conn.execute(
                            "INSERT INTO sessions (token, folder, guest_key, name, photo_count, status,"
                            " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                            (new_token(), folder, key, name, photo_count, STATUS_COLLECTING, now, now))
                        break
                    except sqlite3.IntegrityError:
                        continue
                row = conn.execute("SELECT * FROM sessions WHERE folder=? AND guest_key=?", (folder, key)).fetchone()
                return dict(row), True

            if row["photo_count"] == photo_count and row["name"] == name:
                return dict(row), False
            already_sent = photo_count > row["photo_count"] and row["downloaded_at"] is not None
            conn.execute(
                "UPDATE sessions SET name=?, photo_count=?, updated_at=?,"
                " photos_after_send = CASE WHEN ? THEN 1 ELSE photos_after_send END WHERE id=?",
                (name, photo_count, now, 1 if already_sent else 0, row["id"]))
            return dict(conn.execute("SELECT * FROM sessions WHERE id=?", (row["id"],)).fetchone()), True

    def mark_ready(self, session_id: int, now: float | None = None) -> dict:
        with self._write_lock, self._connect() as conn:
            conn.execute("UPDATE sessions SET status=?, ready_at=COALESCE(ready_at, ?) WHERE id=?",
                         (STATUS_READY, now or time.time(), session_id))
            return dict(conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone())

    def sessions_for(self, folder: str) -> list[dict]:
        """All guests of this photos folder, newest first."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM sessions WHERE folder=? ORDER BY created_at DESC, id DESC",
                                (normalise_folder(folder),)).fetchall()
            return [dict(r) for r in rows]

    def session_by_token(self, token: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE token=?", (token,)).fetchone()
            return dict(row) if row else None

    def session(self, session_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
            return dict(row) if row else None

    def ready_sessions(self, folder: str) -> list[dict]:
        """Guests whose photos are complete, oldest first (the order they appear on the QR screen)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE folder=? AND status='ready' AND photo_count>0"
                " ORDER BY ready_at, id", (normalise_folder(folder),)).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------ guest activity
    def mark_opened(self, session_id: int, now: float | None = None) -> dict:
        """The guest opened their photos page."""
        with self._write_lock, self._connect() as conn:
            conn.execute("UPDATE sessions SET opened_at=COALESCE(opened_at, ?) WHERE id=?",
                         (now or time.time(), session_id))
            return dict(conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone())

    def mark_downloaded(self, session_id: int, now: float | None = None) -> dict:
        """The guest saved their photos. Clears the "new photos since" flag."""
        now = now or time.time()
        with self._write_lock, self._connect() as conn:
            conn.execute("UPDATE sessions SET downloaded_at=?, opened_at=COALESCE(opened_at, ?),"
                         " downloads=downloads+1, photos_after_send=0 WHERE id=?", (now, now, session_id))
            return dict(conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone())
