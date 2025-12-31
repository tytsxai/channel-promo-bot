import asyncio
import contextlib
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


def _log_startup_summary() -> None:
    healthcheck = (
        f"{config.healthcheck_host}:{config.healthcheck_port}"
        if config.healthcheck_port > 0
        else "disabled"
    )
    logger.info(
        "Startup config: env=%s db=%s promo=%02d:%02d UTC rate_limit=%s/%ss "
        "healthcheck=%s log_format=%s log_file=%s openai=%s",
        config.environment,
        config.database_path,
        config.promo_hour_utc,
        config.promo_minute,
        config.rate_limit,
        config.rate_limit_window,
        healthcheck,
        config.log_format,
        config.log_file or "stdout",
        "enabled" if config.openai_api_key else "disabled",
    )


def _warn_on_risky_config() -> None:
    if config.environment.lower() == "production" and config.log_level == "DEBUG":
        logger.warning("LOG_LEVEL=DEBUG in production environment")
    if config.healthcheck_port > 0 and config.healthcheck_host not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        logger.warning(
            "Healthcheck is bound to non-loopback host: %s", config.healthcheck_host
        )


def _set_event_loop_exception_handler(loop: asyncio.AbstractEventLoop) -> None:
    def _handler(_: asyncio.AbstractEventLoop, context: dict) -> None:
        message = context.get("message", "Unhandled exception in event loop")
        exc = context.get("exception")
        if exc:
            logger.error("%s", message, exc_info=exc)
        else:
            logger.error("%s", message)

    loop.set_exception_handler(_handler)


async def _validate_bot(bot: Bot) -> None:
    try:
        me = await bot.get_me()
    except Exception:
        logger.exception("Failed to validate BOT_TOKEN or Telegram connectivity")
        raise
    logger.info("Bot identity verified: id=%s username=@%s", me.id, me.username or "")


async def scheduled_promo(bot: Bot):
    try:
        logger.info("Starting scheduled promo broadcast...")
        sent, failed = await send_promo_to_all(bot)
        logger.info(f"Promo broadcast complete: {sent} sent, {failed} failed")
    except Exception as e:
        logger.exception(f"Scheduled promo failed: {e}")


async def main():
    _log_startup_summary()
    _warn_on_risky_config()

    await init_db()
    logger.info("Database initialized")

    bot = Bot(token=config.bot_token)
    try:
        await _validate_bot(bot)
    except Exception:
        with contextlib.suppress(Exception):
            await bot.session.close()
        raise
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
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            logger.exception("Scheduler shutdown failed")
        if health_server is not None:
            health_server.close()
            await health_server.wait_closed()
        with contextlib.suppress(Exception):
            await bot.session.close()

    loop = asyncio.get_running_loop()
    _set_event_loop_exception_handler(loop)
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
