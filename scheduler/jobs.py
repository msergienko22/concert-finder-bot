"""
Daily scheduled run at configured time (Europe/Amsterdam).
Optional catch-up: run immediately on startup if last run was missed by > 6 hours.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from storage import settings
from pipeline import run as pipeline_run

logger = logging.getLogger(__name__)

CATCH_UP_HOURS = 6
AMSTERDAM = ZoneInfo("Europe/Amsterdam")


async def _do_run(send_message) -> None:
    """Execute pipeline and send notifications."""
    try:
        result = await pipeline_run(send_message)
        status = result.get("status", "?")
        logger.info("Scheduled run finished: status=%s", status)
    except Exception as e:
        logger.exception("Scheduled run failed: %s", e)
        try:
            await send_message(f"Daily run failed: {e}")
        except Exception:
            pass


def _get_send_message(bot, chat_id: int):
    async def send(text: str) -> None:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    return send


async def schedule_daily_run(application) -> None:
    """
    Schedule daily run at user-configured time (Europe/Amsterdam).
    Requires application.bot and notification_chat_id in settings.
    """
    chat_id_raw = await settings.get_setting("notification_chat_id")
    if not chat_id_raw:
        logger.warning("No notification_chat_id set; scheduler not started")
        return
    try:
        chat_id = int(chat_id_raw)
    except ValueError:
        logger.warning("Invalid notification_chat_id; scheduler not started")
        return

    time_str = await settings.get_setting_or_default("check_time_local") or "09:00"
    parts = time_str.strip().split(":")
    hour, minute = 9, 0
    if len(parts) >= 2:
        try:
            hour, minute = int(parts[0]), int(parts[1])
        except ValueError:
            pass
    elif len(parts) == 1 and parts[0].isdigit():
        hour = int(parts[0])

    scheduler = AsyncIOScheduler(timezone=AMSTERDAM)
    send_message = _get_send_message(application.bot, chat_id)

    async def job():
        await _do_run(send_message)

    scheduler.add_job(job, CronTrigger(hour=hour, minute=minute))
    scheduler.start()
    logger.info("Scheduler started: daily at %02d:%02d Europe/Amsterdam", hour, minute)

    # Catch-up: if last run was more than CATCH_UP_HOURS ago, run once now
    last_at = await settings.get_setting("last_run_at")
    if last_at:
        try:
            last_dt = datetime.fromisoformat(last_at.replace("Z", "+00:00"))
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=ZoneInfo("UTC"))
            now = datetime.now(ZoneInfo("UTC"))
            if (now - last_dt).total_seconds() > CATCH_UP_HOURS * 3600:
                logger.info("Catch-up: running now (last run was > %sh ago)", CATCH_UP_HOURS)
                asyncio.create_task(_do_run(send_message))
        except Exception as e:
            logger.debug("Catch-up check skipped: %s", e)
