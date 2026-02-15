"""
Case-insensitive substring matching: events vs artists list.
"""
from typing import List, Tuple

from models import Event

# (artist_from_list, event)
Match = Tuple[str, Event]


def match_events_to_artists(events: List[Event], artists: List[str]) -> List[Match]:
    """
    For each event, if any artist (casefolded) is a substring of the event title (casefolded),
    emit (artist_from_list, event). One event can match multiple artists.
    """
    matches: List[Match] = []
    for event in events:
        title_folded = (event.title or "").casefold()
        for artist in artists:
            a = artist.strip()
            if not a:
                continue
            if a.casefold() in title_folded:
                matches.append((a, event))
    return matches
