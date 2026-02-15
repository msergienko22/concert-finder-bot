"""
Single run: fetch artists → fetch all sources → match → dedupe → notify.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Callable, Awaitable, List, Optional

from models import Event, Source
from storage import settings
from matcher.artists import fetch_artists, get_cached_artists
from matcher.match import match_events_to_artists
from matcher.dedupe import filter_new_matches

logger = logging.getLogger(__name__)

# Connectors registered here (filled when sources are loaded)
_CONNECTORS: List[object] = []


def register_connector(connector: object) -> None:
    _CONNECTORS.append(connector)


async def run(
    send_message: Callable[[str], Awaitable[None]],
    *,
    dry_run: bool = False,
) -> dict:
    """
    Execute one full run. send_message(text) is called for each notification (or for digest).
    Returns dict: status, events_scanned_total, matches_total, notifications_sent, errors_json, artists_fetch_error.
    """
    started_at = datetime.utcnow()
    errors: List[str] = []
    events_all: List[Event] = []
    artists: List[str] = []
    artists_fetch_error: Optional[str] = None

    # 1) Artists list
    url = await settings.get_setting("artists_list_url")
    if not url or not url.strip():
        await settings.set_setting("last_run_at", started_at.isoformat() + "Z")
        await settings.set_setting("last_run_status", "failure")
        await settings.set_setting("last_run_summary_json", json.dumps({"error": "artists_list_url not set"}))
        return {
            "status": "failure",
            "events_scanned_total": 0,
            "matches_total": 0,
            "notifications_sent": 0,
            "errors_json": json.dumps(["artists_list_url not set"]),
            "artists_fetch_error": "artists_list_url not set",
        }
    artists, fetch_err = await fetch_artists(url)
    if fetch_err:
        artists_fetch_error = fetch_err
        artists = await get_cached_artists()
        if artists:
            try:
                await send_message("Artists list URL could not be fetched; using cached list. Error: " + fetch_err)
            except Exception:
                pass
        else:
            await settings.set_setting("last_run_at", started_at.isoformat() + "Z")
            await settings.set_setting("last_run_status", "failure")
            await settings.set_setting("last_run_summary_json", json.dumps({"error": fetch_err}))
            return {
                "status": "failure",
                "events_scanned_total": 0,
                "matches_total": 0,
                "notifications_sent": 0,
                "errors_json": json.dumps([fetch_err]),
                "artists_fetch_error": fetch_err,
            }

    # 2) Fetch events from all connectors
    async def fetch_one(c):
        try:
            return await c.fetch_events()
        except Exception as e:
            logger.warning("Connector %s failed: %s", getattr(c, "source_id", c), e)
            errors.append(f"{getattr(c, 'source_id', 'unknown')}: {e}")
            return []

    results = await asyncio.gather(*[fetch_one(c) for c in _CONNECTORS])
    for c, evs in zip(_CONNECTORS, results):
        events_all.extend(evs)
        sid = getattr(c, "source_id", "?")
        logger.info("Source %s: %d events", sid, len(evs))

    events_scanned_total = len(events_all)
    logger.info(
        "Fetched %d events total; %d artists to match",
        events_scanned_total,
        len(artists),
    )

    # 3) Match
    matches = match_events_to_artists(events_all, artists)
    matches_total = len(matches)
    logger.info("Match result: %d matches (before dedupe)", matches_total)

    # 4) Dedupe (skip_insert when dry_run so we don't record)
    to_notify = await filter_new_matches(matches, skip_insert=dry_run)

    # 5) Notify (digest summary if many matches)
    DIGEST_THRESHOLD = 10
    notifications_sent = 0
    if not dry_run:
        if len(to_notify) > DIGEST_THRESHOLD:
            try:
                await send_message(f"You have {len(to_notify)} new matches. Sending details below.")
            except Exception as e:
                logger.warning("Failed to send digest summary: %s", e)
        for artist, event in to_notify:
            msg = _format_notification(artist, event)
            try:
                await send_message(msg)
                notifications_sent += 1
            except Exception as e:
                logger.warning("Failed to send notification: %s", e)
                errors.append(f"send: {e}")

    finished_at = datetime.utcnow()
    status = "partial_failure" if errors else "success"

    # 6) Persist run summary
    summary = {
        "events_scanned_total": events_scanned_total,
        "matches_total": matches_total,
        "notifications_sent": notifications_sent,
        "errors": errors,
    }
    await settings.set_setting("last_run_at", finished_at.isoformat() + "Z")
    await settings.set_setting("last_run_status", status)
    await settings.set_setting("last_run_summary_json", json.dumps(summary))

    return {
        "status": status,
        "events_scanned_total": events_scanned_total,
        "matches_total": matches_total,
        "notifications_sent": notifications_sent,
        "errors_json": json.dumps(errors),
        "artists_fetch_error": artists_fetch_error,
    }


def _format_notification(artist: str, event: Event) -> str:
    source_name = event.source.value if isinstance(event.source, Source) else str(event.source)
    date_display = event.date_normalized if event.date_normalized != "TBA" else "TBA"
    # Escape Markdown special chars in user content to avoid parse errors
    def esc(s: str) -> str:
        return (s or "").replace("_", "\\_").replace("*", "\\*").replace("[", "\\[")

    return (
        f"🎵 Match found: **{esc(artist)}**\n"
        f"**Event:** {esc(event.title)}\n"
        f"**Venue:** {esc(event.venue)}\n"
        f"**Date:** {date_display}\n"
        f"**Source:** {source_name}\n"
        f"Link: {event.url}"
    )
