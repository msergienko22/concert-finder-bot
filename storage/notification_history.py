"""
Notification history for deduplication: (artist, venue, date_normalized).
"""
from datetime import datetime
from typing import Optional

from storage.db import get_db_path
import aiosqlite


async def exists(artist: str, venue: str, date_normalized: str) -> bool:
    """Return True if this (artist, venue, date_normalized) was already notified."""
    async with aiosqlite.connect(get_db_path()) as conn:
        cursor = await conn.execute(
            """SELECT 1 FROM notification_history
               WHERE artist = ? AND venue = ? AND date_normalized = ?""",
            (artist, venue, date_normalized),
        )
        row = await cursor.fetchone()
        return row is not None


async def insert(
    artist: str,
    venue: str,
    date_normalized: str,
    event_title: Optional[str],
    event_url: Optional[str],
    source: Optional[str],
) -> None:
    """Record that we notified for this (artist, venue, date_normalized)."""
    now = datetime.utcnow().isoformat() + "Z"
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            """INSERT INTO notification_history
               (artist, venue, date_normalized, event_title, event_url, source, first_seen_at, notified_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (artist, venue, date_normalized, event_title or "", event_url or "", source or "", now, now),
        )
        await conn.commit()


async def clear_all() -> int:
    """Delete all notification history. Returns number of rows deleted."""
    async with aiosqlite.connect(get_db_path()) as conn:
        cursor = await conn.execute("DELETE FROM notification_history")
        await conn.commit()
        return cursor.rowcount
