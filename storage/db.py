"""
SQLite database initialization and schema.
"""
import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

_db_path: str = "data/bot.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist TEXT NOT NULL,
    venue TEXT NOT NULL,
    date_normalized TEXT NOT NULL,
    event_title TEXT,
    event_url TEXT,
    source TEXT,
    first_seen_at DATETIME NOT NULL,
    notified_at DATETIME NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_notification_history_dedup
ON notification_history(artist, venue, date_normalized);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at DATETIME NOT NULL,
    finished_at DATETIME,
    status TEXT NOT NULL,
    events_scanned_total INTEGER DEFAULT 0,
    matches_total INTEGER DEFAULT 0,
    notifications_sent INTEGER DEFAULT 0,
    errors_json TEXT
);
"""


def init_db(db_path: str) -> None:
    """Set database path and create schema (sync, for startup)."""
    global _db_path
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _db_path = str(path)
    import sqlite3
    with sqlite3.connect(_db_path) as conn:
        conn.executescript(SCHEMA)
    logger.info("Database initialized at %s", _db_path)


def get_db_path() -> str:
    return _db_path


async def get_connection() -> aiosqlite.Connection:
    """Return an open aiosqlite connection (caller must close)."""
    return await aiosqlite.connect(_db_path)
