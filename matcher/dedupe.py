"""
Dedupe matches against notification_history; return only new (artist, event) to notify.
"""
from typing import List, Tuple

from models import Event
from storage import notification_history as hist

# (artist_from_list, event)
Match = Tuple[str, Event]


async def filter_new_matches(matches: List[Match], *, skip_insert: bool = False) -> List[Match]:
    """
    For each (artist, event), if (artist, venue, date_normalized) is not in history,
    optionally insert into history and add to result. Otherwise skip.
    When skip_insert=True (e.g. dry_run), only return which would be new; do not insert.
    """
    to_notify: List[Match] = []
    for artist, event in matches:
        key_venue = event.venue or ""
        key_date = event.date_normalized or "TBA"
        if await hist.exists(artist, key_venue, key_date):
            continue
        if not skip_insert:
            await hist.insert(
                artist=artist,
                venue=key_venue,
                date_normalized=key_date,
                event_title=event.title,
                event_url=event.url,
                source=event.source.value if hasattr(event.source, "value") else str(event.source),
            )
        to_notify.append((artist, event))
    return to_notify
