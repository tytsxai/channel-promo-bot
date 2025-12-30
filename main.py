import asyncio
import logging
import signal
from datetime import UTC

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.config import config
from src.handlers import admin_handlers, user_handlers
from src.logging_setup import configure_logging
from src.middleware import RateLimitMiddleware
from src.models.database import init_db
from src.services.health_server import start_health_server
from src.services.promo_service import send_promo_to_all

configure_logging(config)
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

    dp.message.middleware(
        RateLimitMiddleware(
            limit=config.rate_limit,
            window=config.rate_limit_window,
            cleanup_interval=config.rate_limit_cleanup,
        )
    )

    dp.include_router(user_handlers.router)
    dp.include_router(admin_handlers.router)

    scheduler = AsyncIOScheduler(timezone=UTC)
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

    health_server = None
    if config.healthcheck_port > 0:
        health_server = await start_health_server(
            config.healthcheck_host, config.healthcheck_port
        )

    shutdown_called = False

    async def shutdown():
        nonlocal shutdown_called
        if shutdown_called:
            return
        shutdown_called = True
        logger.info("Shutting down...")
        scheduler.shutdown(wait=False)
        if health_server is not None:
            health_server.close()
            await health_server.wait_closed()
        await bot.session.close()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
        except NotImplementedError:
            logger.warning("Signal handlers are not supported on this platform")

    logger.info("Bot started")
    try:
        await dp.start_polling(bot)
    finally:
        await shutdown()


if __name__ == "__main__":
    asyncio.run(main())
