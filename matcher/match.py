"""
Case-insensitive substring matching: events vs artists list.
"""
import logging
from typing import List, Tuple

from models import Event

logger = logging.getLogger(__name__)

# (artist_from_list, event)
Match = Tuple[str, Event]


def match_events_to_artists(events: List[Event], artists: List[str]) -> List[Match]:
    """
    For each event, if any artist (casefolded) is a substring of the event title (casefolded),
    emit (artist_from_list, event). One event can match multiple artists.
    """
    artists_clean = [a.strip() for a in artists if a and a.strip()]
    logger.info(
        "Matching: %d artists vs %d events",
        len(artists_clean),
        len(events),
        extra={"artists_count": len(artists_clean), "events_count": len(events)},
    )
    if artists_clean:
        logger.debug("Artists list (first 20): %s", artists_clean[:20])
    matches: List[Match] = []
    match_count_per_artist: dict[str, int] = {a: 0 for a in artists_clean}
    for event in events:
        title_folded = (event.title or "").casefold()
        event_matched = False
        for artist in artists_clean:
            if artist.casefold() in title_folded:
                matches.append((artist, event))
                match_count_per_artist[artist] = match_count_per_artist.get(artist, 0) + 1
                event_matched = True
                logger.info(
                    "Match: artist=%r title=%r source=%s",
                    artist,
                    (event.title or "")[:80],
                    getattr(event.source, "value", event.source),
                )
        if not event_matched:
            logger.debug(
                "No match for event: title=%r source=%s",
                (event.title or "")[:80],
                getattr(event.source, "value", event.source),
            )
    for artist in artists_clean:
        n = match_count_per_artist.get(artist, 0)
        if n == 0:
            logger.info("Artist %r: 0 matches (mismatch)", artist)
        else:
            logger.info("Artist %r: %d matches", artist, n)
    logger.info("Matching done: %d matches", len(matches))
    return matches
