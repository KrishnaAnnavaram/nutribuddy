"""Server-side conversation store (SQLite), keyed by a random session id.

The browser keeps only the session id. The store keeps the condition and the turns,
and it deletes the oldest turns above ``max_turns_stored``.
"""

from __future__ import annotations

import secrets
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS session (
    id TEXT PRIMARY KEY,
    condition TEXT,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS turn (
    session_id TEXT NOT NULL REFERENCES session(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    PRIMARY KEY (session_id, seq)
);
"""


class SessionNotFound(KeyError):
    pass


class SessionStore:
    def __init__(self, path: Path | str, max_turns_stored: int = 40):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._lock = threading.Lock()
        self.max_turns_stored = max_turns_stored

    def create(self, condition: str | None = None) -> str:
        sid = secrets.token_urlsafe(18)
        with self._lock, self._conn:
            self._conn.execute("INSERT INTO session(id, condition, created) VALUES (?, ?, ?)", (sid, condition, time.time()))
        return sid

    def _require(self, sid: str) -> None:
        if not self._conn.execute("SELECT 1 FROM session WHERE id = ?", (sid,)).fetchone():
            raise SessionNotFound(sid)

    def set_condition(self, sid: str, condition: str) -> None:
        with self._lock, self._conn:
            self._require(sid)
            self._conn.execute("UPDATE session SET condition = ? WHERE id = ?", (condition, sid))

    def condition(self, sid: str) -> str | None:
        row = self._conn.execute("SELECT condition FROM session WHERE id = ?", (sid,)).fetchone()
        if row is None:
            raise SessionNotFound(sid)
        return row[0]

    def append(self, sid: str, role: str, content: str) -> None:
        with self._lock, self._conn:
            self._require(sid)
            seq = self._conn.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM turn WHERE session_id = ?", (sid,)).fetchone()[0]
            self._conn.execute("INSERT INTO turn(session_id, seq, role, content) VALUES (?, ?, ?, ?)", (sid, seq, role, content))
            self._conn.execute(
                "DELETE FROM turn WHERE session_id = ? AND seq <= ?", (sid, seq - self.max_turns_stored)
            )

    def history(self, sid: str, last_turns: int) -> list[tuple[str, str]]:
        self._require(sid)
        if last_turns <= 0:
            return []
        rows = self._conn.execute(
            "SELECT role, content FROM turn WHERE session_id = ? ORDER BY seq DESC LIMIT ?", (sid, last_turns)
        ).fetchall()
        return [(r, c) for r, c in reversed(rows)]
