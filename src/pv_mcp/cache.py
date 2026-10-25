"""SQLite cache for openFDA responses. The key never includes an API key."""

import hashlib
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path


class ResponseCache:
    """Store status, body, and the original retrieval time until the TTL passes."""

    def __init__(self, path: Path, *, ttl_seconds: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS responses (
                cache_key TEXT PRIMARY KEY,
                status_code INTEGER NOT NULL,
                body BLOB NOT NULL,
                retrieved_at TEXT NOT NULL,
                expires_at REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    def get(self, key: str, *, now: datetime) -> tuple[int, bytes, str] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT status_code, body, retrieved_at, expires_at
                FROM responses
                WHERE cache_key = ?
                """,
                (key,),
            ).fetchone()
            if row is None:
                return None
            status, body, retrieved_at, expires_at = row
            if float(expires_at) <= now.timestamp():
                self._conn.execute("DELETE FROM responses WHERE cache_key = ?", (key,))
                self._conn.commit()
                return None
            return int(status), bytes(body), str(retrieved_at)

    def put(
        self,
        key: str,
        status_code: int,
        body: bytes,
        retrieved_at: str,
        *,
        now: datetime,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO responses (cache_key, status_code, body, retrieved_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    status_code = excluded.status_code,
                    body = excluded.body,
                    retrieved_at = excluded.retrieved_at,
                    expires_at = excluded.expires_at
                """,
                (key, status_code, body, retrieved_at, now.timestamp() + self._ttl),
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def cache_key(path: str, params: dict[str, str]) -> str:
    """Hash the public query. Callers must omit api_key before calling this."""

    payload = json.dumps(
        {"path": path, "params": sorted(params.items())},
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()
