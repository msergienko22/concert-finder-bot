"""
Amsterdam Concert Tracker — single-user Telegram bot entrypoint.
"""
import os
import sys
import logging

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN is not set")
        sys.exit(1)

    # Database path: ensure data dir exists (storage will init schema)
    db_path = os.environ.get("DATABASE_PATH", "data/bot.db")
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    from storage.db import init_db
    init_db(db_path)

    # Register all source connectors for the pipeline
    from pipeline import register_connector
    from sources.paradiso import ParadisoConnector
    from sources.melkweg import MelkwegConnector
    from sources.afas_live import AFASLiveConnector
    from sources.ziggo_dome import ZiggoDomeConnector
    from sources.ticketmaster_nl import TicketmasterNLConnector
    from sources.johan_cruijff_arena import JohanCruijffArenaConnector
    register_connector(ParadisoConnector())
    register_connector(MelkwegConnector())
    register_connector(AFASLiveConnector())
    register_connector(ZiggoDomeConnector())
    register_connector(TicketmasterNLConnector())
    register_connector(JohanCruijffArenaConnector())

    from telegram import Update
    from telegram.ext import Application
    from bot.handlers import register_handlers
    from scheduler.jobs import schedule_daily_run

    async def post_init(app):
        logger.info("Bot initialized")
        await schedule_daily_run(app)

    application = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .build()
    )
    register_handlers(application)

    logger.info("Starting polling")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
