"""
Base connector: fetch_events() with rate limiting and retries.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List

import httpx

from models import Event

logger = logging.getLogger(__name__)

USER_AGENT = "AmsterdamConcertTracker/1.0 (NL concert notifications; bot)"
CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 30.0
RETRIES = 4
BACKOFF_BASE = 1.0  # 1s, 2s, 4s, 8s
RATE_LIMIT_DELAY = 1.0  # seconds between requests per connector


async def _rate_limit() -> None:
    await asyncio.sleep(RATE_LIMIT_DELAY)


async def fetch_with_retries(
    client: httpx.AsyncClient,
    url: str,
    *,
    method: str = "GET",
) -> httpx.Response:
    """GET (or method) with exponential backoff retries. Raises last exception after retries."""
    last_exc: Exception = None
    for attempt in range(RETRIES):
        try:
            resp = await client.request(method, url)
            resp.raise_for_status()
            return resp
        except (httpx.HTTPError, httpx.RequestError) as e:
            last_exc = e
            if attempt < RETRIES - 1:
                delay = BACKOFF_BASE * (2**attempt)
                logger.warning("Attempt %s failed for %s: %s; retry in %ss", attempt + 1, url, e, delay)
                await asyncio.sleep(delay)
    raise last_exc  # type: ignore


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(CONNECT_TIMEOUT, read=READ_TIMEOUT),
        headers={"User-Agent": USER_AGENT},
    )


class BaseConnector(ABC):
    """Abstract event source. Subclasses implement fetch_events()."""

    @property
    @abstractmethod
    def source_id(self) -> str:
        """Used for Event.source and logging."""
        ...

    @abstractmethod
    async def fetch_events(self) -> List[Event]:
        """Fetch and normalize events. Return empty list on parse failure; do not raise."""
        ...
