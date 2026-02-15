"""
Paradiso Amsterdam events connector.
"""
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models import Event, Source
from sources.base import BaseConnector, fetch_with_retries, make_client, _rate_limit

AGENDA_URL = "https://www.paradiso.nl/en/landing/concertagenda-paradiso/2069817"
DEFAULT_VENUE = "Paradiso"
# Month abbreviations on site: Jan, Feb, Mar, ...
MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
# Link text often "Fr 20 Mar", "Th 19 Mar" etc. — day number + month
DATE_PATTERN = re.compile(r"(?:Mo|Tu|We|Th|Fr|Sa|Su)\s+(\d{1,2})\s+([A-Za-z]{3})", re.IGNORECASE)


def _normalize_date(date_raw: str) -> str:
    """Return YYYY-MM-DD or TBA."""
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
    # If month is in the past this year, assume next year
    now = datetime.utcnow()
    if month < now.month or (month == now.month and day < now.day):
        year += 1
    try:
        d = datetime(year, month, day)
        return d.strftime("%Y-%m-%d")
    except ValueError:
        return "TBA"


def _extract_venue_from_text(text: str) -> str:
    """If text mentions a known sub-venue, return it; else Paradiso."""
    t = text.lower()
    if "bitterzoet" in t:
        return "Bitterzoet"
    if "tolhuistuin" in t:
        return "Tolhuistuin"
    if "cinetol" in t:
        return "Cinetol"
    if "zonnehuis" in t:
        return "Zonnehuis"
    if "vondelkerk" in t:
        return "Vondelkerk"
    if "de duif" in t:
        return "De Duif"
    if "afas live" in t:
        return "AFAS Live"
    return DEFAULT_VENUE


class ParadisoConnector(BaseConnector):
    @property
    def source_id(self) -> str:
        return Source.PARADISO.value

    async def fetch_events(self) -> list[Event]:
        events: list[Event] = []
        try:
            await _rate_limit()
            async with make_client() as client:
                resp = await fetch_with_retries(client, AGENDA_URL)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Paradiso fetch failed: %s", e)
            return events

        try:
            soup = BeautifulSoup(resp.text, "html.parser")
            base = "https://www.paradiso.nl"
            # Find event links: /en/program/... 
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                if "/en/program/" not in href or "/landing/" in href:
                    continue
                url = urljoin(base, href)
                title = (a.get_text() or "").strip()
                if not title or len(title) < 2:
                    continue
                # First part of link text often "Fr 20 Mar" or similar
                date_raw = title[:20] if len(title) > 20 else title
                date_normalized = _normalize_date(title)
                venue = _extract_venue_from_text(title)
                events.append(
                    Event(
                        source=Source.PARADISO,
                        title=title,
                        venue=venue,
                        date_raw=date_raw,
                        date_normalized=date_normalized,
                        url=url,
                    )
                )
            # Dedupe by url (same event can appear in multiple blocks)
            seen_urls: set[str] = set()
            unique: list[Event] = []
            for e in events:
                if e.url not in seen_urls:
                    seen_urls.add(e.url)
                    unique.append(e)
            return unique
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Paradiso parse error: %s", e)
            return []
