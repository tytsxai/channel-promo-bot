import asyncio
import logging
import signal
from datetime import timezone
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.config import config
from src.models.database import init_db
from src.handlers import user_handlers, admin_handlers
from src.services.promo_service import send_promo_to_all
from src.middleware import RateLimitMiddleware

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def scheduled_promo(bot: Bot):
    try:
        logger.info("Starting scheduled promo broadcast...")
        sent, failed = await send_promo_to_all(bot)
        logger.info(f"Promo broadcast complete: {sent} sent, {failed} failed")
    except Exception as e:
        logger.exception(f"Scheduled promo failed: {e}")


async def main():
    await init_db()
    logger.info("Database initialized")

    bot = Bot(token=config.bot_token)
    dp = Dispatcher()

    dp.message.middleware(RateLimitMiddleware(limit=10, window=60))

    dp.include_router(user_handlers.router)
    dp.include_router(admin_handlers.router)

    scheduler = AsyncIOScheduler(timezone=timezone.utc)
    scheduler.add_job(
        scheduled_promo,
        "cron",
        hour=config.promo_hour_utc,
        minute=config.promo_minute,
        args=[bot],
        max_instances=1,
        misfire_grace_time=300,
    )
    scheduler.start()
    logger.info(
        f"Scheduler started, promo at {config.promo_hour_utc}:{config.promo_minute:02d} UTC"
    )

    async def shutdown():
        logger.info("Shutting down...")
        scheduler.shutdown(wait=False)
        await bot.session.close()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))

    logger.info("Bot started")
    try:
        await dp.start_polling(bot)
    finally:
        await shutdown()


if __name__ == "__main__":
    asyncio.run(main())
