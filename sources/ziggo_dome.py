"""
Ziggo Dome Amsterdam events connector.
Page structure may be JS-heavy; we try to parse what we can.
"""
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models import Event, Source
from sources.base import BaseConnector, fetch_with_retries, make_client, _rate_limit

AGENDA_URL = "https://www.ziggodome.nl/agenda"
DEFAULT_VENUE = "Ziggo Dome"


class ZiggoDomeConnector(BaseConnector):
    @property
    def source_id(self) -> str:
        return Source.ZIGGO_DOME.value

    async def fetch_events(self) -> list[Event]:
        events: list[Event] = []
        try:
            await _rate_limit()
            async with make_client() as client:
                resp = await fetch_with_retries(client, AGENDA_URL)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Ziggo Dome fetch failed: %s", e)
            return events
        try:
            soup = BeautifulSoup(resp.text, "html.parser")
            base = "https://www.ziggodome.nl"
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                if not href or "agenda" in href or href == "/":
                    continue
                text = (a.get_text() or "").strip()
                if len(text) < 3 or len(text) > 200:
                    continue
                url = urljoin(base, href)
                if url == base or url == base + "/":
                    continue
                events.append(
                    Event(
                        source=Source.ZIGGO_DOME,
                        title=text,
                        venue=DEFAULT_VENUE,
                        date_raw="TBA",
                        date_normalized="TBA",
                        url=url,
                    )
                )
            seen: set[str] = set()
            unique = [e for e in events if e.url not in seen and not seen.add(e.url)]
            return unique[:200]  # cap in case of noisy page
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Ziggo Dome parse error: %s", e)
            return []
