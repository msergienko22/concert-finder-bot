"""
First-run onboarding wizard: artists URL → location → check time.
"""
import re
import logging

from telegram import Update
from telegram.ext import ContextTypes
import httpx

from storage import settings
from matcher.artists import fetch_artists, get_cached_artists, CACHE_KEY

logger = logging.getLogger(__name__)

STEP_KEY = "onboarding_step"
STEP_URL = "url"
STEP_LOCATION = "location"
STEP_TIME = "time"

PROMPT_URL = (
    "Send the URL to your GitHub-hosted .txt list (one artist per line).\n"
    "Example: https://raw.githubusercontent.com/username/repo/main/artists.txt"
)
PROMPT_LOCATION = "Location? For MVP only Netherlands is supported. Send: NL"
PROMPT_TIME = (
    "Daily check time? Send HH:MM in Europe/Amsterdam (e.g. 09:00). Default is 09:00."
)
TIME_REGEX = re.compile(r"^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$")


async def get_step() -> str:
    return await settings.get_setting(STEP_KEY) or ""


async def set_step(step: str) -> None:
    await settings.set_setting(STEP_KEY, step)


async def needs_onboarding() -> bool:
    """True if artists_list_url is not set."""
    url = await settings.get_setting("artists_list_url")
    return url is None or url.strip() == ""


async def handle_onboarding_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    If user is in onboarding, handle their message and return True.
    Otherwise return False so the main handler can process it.
    """
    step = await get_step()
    if not step:
        return False

    text = (update.message and update.message.text) or ""
    if not text.strip():
        await update.message.reply_text("Please send a non-empty message.")
        return True

    if step == STEP_URL:
        return await _handle_url_step(update, text.strip())
    if step == STEP_LOCATION:
        return await _handle_location_step(update, text.strip())
    if step == STEP_TIME:
        return await _handle_time_step(update, text.strip())
    return False


async def _handle_url_step(update: Update, text: str) -> bool:
    if not text.startswith("http://") and not text.startswith("https://"):
        await update.message.reply_text("Please send a valid URL (http or https).")
        return True
    # Validate: fetch once
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            r = await client.get(text, headers={"User-Agent": "AmsterdamConcertTracker/1.0"})
            r.raise_for_status()
            body = r.text
    except Exception as e:
        await update.message.reply_text(f"Could not fetch that URL: {e}. Please try another.")
        return True
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    if not lines:
        await update.message.reply_text("The file is empty or has no valid lines. Please use a .txt with one artist per line.")
        return True
    await settings.set_setting("artists_list_url", text)
    await settings.set_setting(CACHE_KEY, "\n".join(lines))
    await set_step(STEP_LOCATION)
    await update.message.reply_text(PROMPT_LOCATION)
    return True


async def _handle_location_step(update: Update, text: str) -> bool:
    if text.upper() != "NL":
        await update.message.reply_text("For MVP only NL (Netherlands) is supported. Please send: NL")
        return True
    await settings.set_setting("location", "NL")
    await set_step(STEP_TIME)
    await update.message.reply_text(PROMPT_TIME)
    return True


async def _handle_time_step(update: Update, text: str) -> bool:
    m = TIME_REGEX.match(text.strip())
    if not m:
        await update.message.reply_text("Please send time as HH:MM (e.g. 09:00).")
        return True
    await settings.set_setting("check_time_local", text.strip())
    await settings.set_setting("timezone", "Europe/Amsterdam")
    await set_step("")
    await update.message.reply_text(
        "Setup complete. I'll check for concerts daily at " + text.strip() + " (Europe/Amsterdam). "
        "Use /settings to see your config and /run_now to run a check now."
    )
    return True


async def start_onboarding(update: Update) -> None:
    """Set step to URL and send first prompt."""
    await set_step(STEP_URL)
    await update.message.reply_text(PROMPT_URL)
