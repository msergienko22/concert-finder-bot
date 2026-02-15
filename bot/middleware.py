"""
Single-user auth: only authorized_user_id can use the bot.
"""
import os
from typing import Callable, Awaitable

from telegram import Update
from telegram.ext import ContextTypes

from storage import settings

REJECT_MESSAGE = "This bot is private."


async def get_authorized_user_id() -> int | None:
    """Return stored authorized_user_id, or from env, or None (not set yet)."""
    env_id = os.environ.get("AUTHORIZED_USER_ID")
    if env_id is not None:
        try:
            return int(env_id)
        except ValueError:
            pass
    raw = await settings.get_setting("authorized_user_id")
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


async def is_authorized(update: Update) -> bool:
    """True if update is from the authorized user or we're still in onboarding (no auth set)."""
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        return False
    auth_id = await get_authorized_user_id()
    if auth_id is None:
        return True  # First user to interact becomes authorized
    return user_id == auth_id


async def auth_middleware(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    next_handler: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]],
) -> None:
    """Call next_handler only if user is authorized; else reply and return."""
    if not await is_authorized(update):
        if update.message:
            await update.message.reply_text(REJECT_MESSAGE)
        return
    await next_handler(update, context)
