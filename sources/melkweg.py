"""
Melkweg Amsterdam events connector.
"""
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models import Event, Source
from sources.base import BaseConnector, fetch_with_retries, make_client, _rate_limit

AGENDA_URL = "https://www.melkweg.nl/en/agenda"
DEFAULT_VENUE = "Melkweg"
MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
DATE_PATTERN = re.compile(r"(?:Su|Mo|Tu|We|Th|Fr|Sa)\s+(\d{1,2})\s+([A-Za-z]{3})", re.IGNORECASE)


def _normalize_date(date_raw: str) -> str:
    m = DATE_PATTERN.search(date_raw)
    if not m:
        return "TBA"
    day_s, mon_s = m.group(1), m.group(2).lower()[:3]
    month = MONTHS.get(mon_s)
    if month is None:
        return "TBA"
    try:
        day = int(day_s)
    except ValueError:
        return "TBA"
    year = datetime.utcnow().year
    now = datetime.utcnow()
    if month < now.month or (month == now.month and day < now.day):
        year += 1
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return "TBA"


class MelkwegConnector(BaseConnector):
    @property
    def source_id(self) -> str:
        return Source.MELKWEG.value

    async def fetch_events(self) -> list[Event]:
        events: list[Event] = []
        try:
            await _rate_limit()
            async with make_client() as client:
                resp = await fetch_with_retries(client, AGENDA_URL)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Melkweg fetch failed: %s", e)
            return events
        try:
            soup = BeautifulSoup(resp.text, "html.parser")
            base = "https://www.melkweg.nl"
            # Find headings (event names) and nearby links
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                if "/en/" not in href or "agenda" in href:
                    continue
                text = (a.get_text() or "").strip()
                if len(text) < 2:
                    continue
                url = urljoin(base, href)
                date_normalized = _normalize_date(text)
                events.append(
                    Event(
                        source=Source.MELKWEG,
                        title=text,
                        venue=DEFAULT_VENUE,
                        date_raw=text[:30],
                        date_normalized=date_normalized,
                        url=url,
                    )
                )
            seen: set[str] = set()
            unique = [e for e in events if e.url not in seen and not seen.add(e.url)]
            return unique
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Melkweg parse error: %s", e)
            return []
