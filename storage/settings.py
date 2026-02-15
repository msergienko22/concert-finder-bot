"""
Key-value settings in SQLite.
"""
import logging
from typing import Optional

from storage.db import get_db_path
import aiosqlite

logger = logging.getLogger(__name__)

DEFAULTS = {
    "location": "NL",
    "check_time_local": "09:00",
    "timezone": "Europe/Amsterdam",
}


async def get_setting(key: str) -> Optional[str]:
    """Return value for key, or None if not set."""
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row["value"] if row else None


async def get_setting_or_default(key: str) -> str:
    """Return value for key, or default from DEFAULTS, or empty string."""
    value = await get_setting(key)
    if value is not None:
        return value
    return DEFAULTS.get(key, "")


async def set_setting(key: str, value: str) -> None:
    """Set key to value."""
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        await conn.commit()
