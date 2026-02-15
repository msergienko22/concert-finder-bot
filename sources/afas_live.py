"""
AFAS Live Amsterdam events connector.
"""
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models import Event, Source
from sources.base import BaseConnector, fetch_with_retries, make_client, _rate_limit

AGENDA_URL = "https://www.afaslive.nl/en/agenda"
DEFAULT_VENUE = "AFAS Live"
MONTHS = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
          "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12}
# "Monday 16 February 2026" or "Friday 20 February 2026"
DATE_PATTERN = re.compile(r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})", re.IGNORECASE)


def _normalize_date(date_raw: str) -> str:
    m = DATE_PATTERN.search(date_raw)
    if not m:
        return "TBA"
    day_s, month_s, year_s = m.group(1), m.group(2).lower(), m.group(3)
    month = MONTHS.get(month_s)
    if month is None:
        return "TBA"
    try:
        day, year = int(day_s), int(year_s)
    except ValueError:
        return "TBA"
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return "TBA"


class AFASLiveConnector(BaseConnector):
    @property
    def source_id(self) -> str:
        return Source.AFAS_LIVE.value

    async def fetch_events(self) -> list[Event]:
        events: list[Event] = []
        try:
            await _rate_limit()
            async with make_client() as client:
                resp = await fetch_with_retries(client, AGENDA_URL)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("AFAS Live fetch failed: %s", e)
            return events
        try:
            soup = BeautifulSoup(resp.text, "html.parser")
            base = "https://www.afaslive.nl"
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                if "/en/agenda/" not in href or href.endswith("/agenda"):
                    continue
                text = (a.get_text() or "").strip()
                if len(text) < 2:
                    continue
                url = urljoin(base, href)
                date_normalized = _normalize_date(text)
                # Title: first part before date-like text (e.g. "David Byrne Monday 16 February 2026" -> "David Byrne")
                title = text
                events.append(
                    Event(
                        source=Source.AFAS_LIVE,
                        title=title,
                        venue=DEFAULT_VENUE,
                        date_raw=text[:50],
                        date_normalized=date_normalized,
                        url=url,
                    )
                )
            seen: set[str] = set()
            unique = [e for e in events if e.url not in seen and not seen.add(e.url)]
            return unique
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("AFAS Live parse error: %s", e)
            return []
