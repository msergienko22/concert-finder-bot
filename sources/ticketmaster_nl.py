"""
Ticketmaster NL events connector.
Uses scraping; for production an API key (Discovery API) can be added later.
"""
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models import Event, Source
from sources.base import BaseConnector, fetch_with_retries, make_client, _rate_limit

# Concerts listing for Netherlands
EVENTS_URL = "https://www.ticketmaster.nl/music"
DEFAULT_VENUE = "Ticketmaster NL"
MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "mei": 5, "jun": 6, "jul": 7,
          "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12}


def _normalize_date(date_raw: str) -> str:
    # Try DD-MM-YYYY or DD month YYYY
    m = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", date_raw)
    if m:
        try:
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            pass
    for name, num in MONTHS.items():
        if name in date_raw.lower():
            mm = re.search(r"(\d{1,2})\s*" + name, date_raw, re.I)
            if mm:
                try:
                    day = int(mm.group(1))
                    year = datetime.utcnow().year
                    if num < datetime.utcnow().month:
                        year += 1
                    return datetime(year, num, day).strftime("%Y-%m-%d")
                except ValueError:
                    pass
    return "TBA"


class TicketmasterNLConnector(BaseConnector):
    @property
    def source_id(self) -> str:
        return Source.TICKETMASTER.value

    async def fetch_events(self) -> list[Event]:
        events: list[Event] = []
        try:
            await _rate_limit()
            async with make_client() as client:
                resp = await fetch_with_retries(client, EVENTS_URL)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Ticketmaster NL fetch failed: %s", e)
            return events
        try:
            soup = BeautifulSoup(resp.text, "html.parser")
            base = "https://www.ticketmaster.nl"
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                if "/event/" not in href and "/music/" not in href:
                    continue
                if "music" == href.strip("/").split("/")[-1]:
                    continue
                text = (a.get_text() or "").strip()
                if len(text) < 2:
                    continue
                url = urljoin(base, href)
                date_normalized = _normalize_date(text)
                events.append(
                    Event(
                        source=Source.TICKETMASTER,
                        title=text,
                        venue=DEFAULT_VENUE,
                        date_raw=text[:50],
                        date_normalized=date_normalized,
                        url=url,
                    )
                )
            seen: set[str] = set()
            unique = [e for e in events if e.url not in seen and not seen.add(e.url)]
            return unique[:500]
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Ticketmaster NL parse error: %s", e)
            return []
