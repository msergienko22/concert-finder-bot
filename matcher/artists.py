"""
Fetch and parse artists list from URL; cache for fallback on failure.
"""
import logging
from typing import List, Optional, Tuple

import httpx
from storage import settings

logger = logging.getLogger(__name__)

CACHE_KEY = "artists_list_cached"
USER_AGENT = "AmsterdamConcertTracker/1.0 (NL concert notifications bot)"
CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 30.0


def _parse_lines(text: str) -> List[str]:
    """Dedupe, strip, skip empty. Return list of artist strings."""
    seen: set[str] = set()
    out: List[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


async def fetch_artists(url: str) -> Tuple[List[str], Optional[str]]:
    """
    Fetch artists list from URL. Returns (artists, error_message).
    On success: updates cache and returns (list, None).
    On failure: returns ([], error_message); if cache exists, also return cached list in a second call
    pattern: caller should check error and then call get_cached_artists() if needed.
    """
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(CONNECT_TIMEOUT, read=READ_TIMEOUT),
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            text = resp.text
    except Exception as e:
        logger.warning("Artists list fetch failed: %s", e)
        return ([], str(e))

    artists = _parse_lines(text)
    if not artists:
        return ([], "Artists list is empty after parsing")
    # Cache as newline-joined
    await settings.set_setting(CACHE_KEY, "\n".join(artists))
    return (artists, None)


async def get_cached_artists() -> List[str]:
    """Return last successfully fetched artists list from cache, or empty list."""
    raw = await settings.get_setting(CACHE_KEY)
    if not raw:
        return []
    return _parse_lines(raw)
