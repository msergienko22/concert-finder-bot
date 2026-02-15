"""
Telegram command handlers: /start, /help, /settings, /set_*, etc.
"""
import json
import re
import os
import logging

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
import httpx

from storage import settings
from storage import notification_history as notif_hist
from bot.middleware import is_authorized, get_authorized_user_id, REJECT_MESSAGE
from bot.onboarding import needs_onboarding, start_onboarding, handle_onboarding_message, get_step

logger = logging.getLogger(__name__)

# Confirmation for reset: user must send this within context
RESET_CONFIRM_CMD = "reset_history_confirm"

TIME_REGEX = re.compile(r"^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$")


async def _require_auth(update: Update) -> bool:
    if not await is_authorized(update):
        if update.message:
            await update.message.reply_text(REJECT_MESSAGE)
        return False
    return True


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_authorized(update):
        if update.message:
            await update.message.reply_text(REJECT_MESSAGE)
        return
    # Set authorized user on first /start if not set
    auth_id = await get_authorized_user_id()
    if auth_id is None and update.effective_user:
        await settings.set_setting("authorized_user_id", str(update.effective_user.id))
    # Remember chat for notifications
    if update.effective_chat:
        await settings.set_setting("notification_chat_id", str(update.effective_chat.id))

    if await needs_onboarding():
        await start_onboarding(update)
        return

    # Already configured: show settings and next run
    url = await settings.get_setting_or_default("artists_list_url")
    loc = await settings.get_setting_or_default("location")
    t = await settings.get_setting_or_default("check_time_local") or "09:00"
    tz = await settings.get_setting_or_default("timezone") or "Europe/Amsterdam"
    await update.message.reply_text(
        f"Current settings:\n"
        f"• Artists list: {url or '(not set)'}\n"
        f"• Location: {loc or 'NL'}\n"
        f"• Daily check: {t} ({tz})\n\n"
        f"Use /settings, /run_now, /status, or /help."
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_auth(update):
        return
    await update.message.reply_text(
        "Commands:\n"
        "/start — Show settings or start setup\n"
        "/help — This message\n"
        "/settings — Show current settings\n"
        "/set_artists_url <url> — Set your artists list URL (GitHub raw .txt)\n"
        "/set_time <HH:MM> — Daily check time (Europe/Amsterdam)\n"
        "/set_location NL — Location (MVP: NL only)\n"
        "/run_now — Run a full check now\n"
        "/status — Last run time and counts\n"
        "/reset_history — Clear notification history (you'll get confirmations again)\n"
        "/sources — List monitored sources\n"
        "/dry_run — Run check and report matches without sending notifications\n\n"
        "Matching: case-insensitive substring. If an artist name appears in the event title, you get notified once per (artist, venue, date)."
    )


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_auth(update):
        return
    url = await settings.get_setting_or_default("artists_list_url")
    loc = await settings.get_setting_or_default("location")
    t = await settings.get_setting_or_default("check_time_local") or "09:00"
    tz = await settings.get_setting_or_default("timezone") or "Europe/Amsterdam"
    await update.message.reply_text(
        f"Artists list URL: {url or '(not set)'}\n"
        f"Location: {loc or 'NL'}\n"
        f"Check time: {t} ({tz})"
    )


async def cmd_set_artists_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_auth(update):
        return
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Usage: /set_artists_url <url>")
        return
    url = context.args[0].strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        await update.message.reply_text("URL must start with http:// or https://")
        return
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            r = await client.get(url, headers={"User-Agent": "AmsterdamConcertTracker/1.0"})
            r.raise_for_status()
            body = r.text
    except Exception as e:
        await update.message.reply_text(f"Could not fetch URL: {e}")
        return
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    if not lines:
        await update.message.reply_text("URL returned no lines. Use a .txt with one artist per line.")
        return
    await settings.set_setting("artists_list_url", url)
    from matcher.artists import CACHE_KEY
    await settings.set_setting(CACHE_KEY, "\n".join(lines))
    await update.message.reply_text("Artists list URL updated and verified.")


async def cmd_set_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_auth(update):
        return
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Usage: /set_time <HH:MM> (e.g. 09:00)")
        return
    raw = context.args[0].strip()
    if not TIME_REGEX.match(raw):
        await update.message.reply_text("Please use HH:MM format (e.g. 09:00).")
        return
    await settings.set_setting("check_time_local", raw)
    await settings.set_setting("timezone", "Europe/Amsterdam")
    await update.message.reply_text(f"Daily check time set to {raw} (Europe/Amsterdam).")


async def cmd_set_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_auth(update):
        return
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Usage: /set_location NL (MVP: NL only)")
        return
    loc = context.args[0].strip().upper()
    if loc != "NL":
        await update.message.reply_text("For MVP only NL is supported.")
        return
    await settings.set_setting("location", "NL")
    await update.message.reply_text("Location set to NL.")


async def cmd_run_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_auth(update):
        return
    chat_id = await settings.get_setting("notification_chat_id")
    if not chat_id:
        await update.message.reply_text("Send /start first so I know where to send notifications.")
        return
    await update.message.reply_text("Running check…")
    bot = context.application.bot

    async def send_message(text: str) -> None:
        await bot.send_message(chat_id=int(chat_id), text=text, parse_mode="Markdown")

    from pipeline import run as pipeline_run
    result = await pipeline_run(send_message)
    status = result.get("status", "?")
    scanned = result.get("events_scanned_total", 0)
    matches = result.get("matches_total", 0)
    sent = result.get("notifications_sent", 0)
    await update.message.reply_text(
        f"Run finished. Status: {status}\n"
        f"Events scanned: {scanned}, Matches: {matches}, Notifications sent: {sent}"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_auth(update):
        return
    last_at = await settings.get_setting("last_run_at")
    last_status = await settings.get_setting("last_run_status")
    summary_raw = await settings.get_setting("last_run_summary_json")
    if not last_at:
        await update.message.reply_text("No run yet. Use /run_now to run a check.")
        return
    try:
        summary = json.loads(summary_raw) if summary_raw else {}
    except Exception:
        summary = {}
    scanned = summary.get("events_scanned_total", "?")
    matches = summary.get("matches_total", "?")
    sent = summary.get("notifications_sent", "?")
    errors = summary.get("errors", [])
    err_text = "; ".join(errors[:3]) if errors else "none"
    await update.message.reply_text(
        f"Last run: {last_at}\n"
        f"Outcome: {last_status}\n"
        f"Events scanned: {scanned}, Matches: {matches}, Notifications sent: {sent}\n"
        f"Errors: {err_text}"
    )


async def cmd_reset_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_auth(update):
        return
    await update.message.reply_text(
        "This will clear all notification history so you can receive the same matches again. "
        f"Reply /{RESET_CONFIRM_CMD} to confirm."
    )


async def cmd_reset_history_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_auth(update):
        return
    n = await notif_hist.clear_all()
    await update.message.reply_text(f"Notification history cleared ({n} entries).")


async def cmd_sources(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_auth(update):
        return
    await update.message.reply_text(
        "Monitored sources:\n"
        "• Ticketmaster NL\n"
        "• Paradiso\n"
        "• Melkweg\n"
        "• AFAS Live\n"
        "• Ziggo Dome\n"
        "• Johan Cruijff ArenA"
    )


async def cmd_dry_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_auth(update):
        return
    chat_id = await settings.get_setting("notification_chat_id")
    if not chat_id:
        await update.message.reply_text("Send /start first.")
        return
    await update.message.reply_text("Running dry run (no notifications will be sent)…")
    bot = context.application.bot

    async def noop_send(_text: str) -> None:
        pass

    from pipeline import run as pipeline_run
    result = await pipeline_run(noop_send, dry_run=True)
    status = result.get("status", "?")
    scanned = result.get("events_scanned_total", 0)
    matches = result.get("matches_total", 0)
    await update.message.reply_text(
        f"Dry run finished. Status: {status}\n"
        f"Events scanned: {scanned}, Matches found: {matches} (no notifications sent)."
    )


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route messages: onboarding step or unknown."""
    if not await is_authorized(update):
        if update.message:
            await update.message.reply_text(REJECT_MESSAGE)
        return
    if await handle_onboarding_message(update, context):
        return
    if update.message:
        await update.message.reply_text("Send /help for commands.")


def register_handlers(application) -> None:
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("settings", cmd_settings))
    application.add_handler(CommandHandler("set_artists_url", cmd_set_artists_url))
    application.add_handler(CommandHandler("set_time", cmd_set_time))
    application.add_handler(CommandHandler("set_location", cmd_set_location))
    application.add_handler(CommandHandler("run_now", cmd_run_now))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("reset_history", cmd_reset_history))
    application.add_handler(CommandHandler(RESET_CONFIRM_CMD, cmd_reset_history_confirm))
    application.add_handler(CommandHandler("sources", cmd_sources))
    application.add_handler(CommandHandler("dry_run", cmd_dry_run))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
