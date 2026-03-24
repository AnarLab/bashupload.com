import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from app.config import DB_PATH

_lock = threading.Lock()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS uploads (
                token TEXT NOT NULL,
                filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                downloads INTEGER NOT NULL DEFAULT 0,
                max_downloads INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (token, filename)
            )
            """
        )
        conn.commit()


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def insert_upload(
    token: str,
    filename: str,
    stored_path: Path,
    ttl_seconds: int,
    max_downloads: int,
) -> None:
    now = time.time()
    expires = now + ttl_seconds
    with _lock:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO uploads (token, filename, stored_path, created_at, expires_at, downloads, max_downloads)
                VALUES (?, ?, ?, ?, ?, 0, ?)
                """,
                (token, filename, str(stored_path), now, expires, max_downloads),
            )
            conn.commit()


def try_claim_download(token: str, filename: str) -> Path | None:
    with _lock:
        with _connect() as conn:
            row = conn.execute(
                "SELECT * FROM uploads WHERE token = ? AND filename = ?",
                (token, filename),
            ).fetchone()
            if row is None:
                return None
            now = time.time()
            if now > row["expires_at"]:
                return None
            if row["downloads"] >= row["max_downloads"]:
                return None
            conn.execute(
                "UPDATE uploads SET downloads = downloads + 1 WHERE token = ? AND filename = ?",
                (token, filename),
            )
            conn.commit()
            return Path(row["stored_path"])


def delete_upload(token: str, filename: str) -> None:
    with _lock:
        with _connect() as conn:
            conn.execute(
                "DELETE FROM uploads WHERE token = ? AND filename = ?",
                (token, filename),
            )
            conn.commit()
