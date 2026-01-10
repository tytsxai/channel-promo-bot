import asyncio
import contextlib
import logging
import os
import signal
import socket
from datetime import UTC

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    BotCommandScopeDefault,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.config import config
from src.handlers import admin_handlers, user_handlers
from src.logging_setup import configure_logging
from src.middleware import RateLimitMiddleware
from src.models.database import init_db
from src.services.health_server import start_health_server
from src.services.instance_lock import (
    InstanceLockError,
    acquire_instance_lock,
    release_instance_lock,
)
from src.services.lock_service import acquire_lock, refresh_lock, release_lock
from src.services.promo_service import send_promo_to_all

configure_logging(config)
logger = logging.getLogger(__name__)
_INSTANCE_ID = f"{socket.gethostname()}:{os.getpid()}"
_PROMO_LOCK_NAME = "scheduled_promo"


class _CancelToken:
    def __init__(self, *events: asyncio.Event):
        self._events = events

    def is_set(self) -> bool:
        return any(event.is_set() for event in self._events)


def _log_startup_summary() -> None:
    healthcheck = (
        f"{config.healthcheck_host}:{config.healthcheck_port}"
        if config.healthcheck_port > 0
        else "disabled"
    )
    logger.info(
        "Startup config: env=%s db=%s promo=%02d:%02d UTC "
        "promo_concurrency=%s promo_interval=%ss promo_lock=%s promo_batch=%s "
        "rate_limit=%s/%ss rate_limit_storage=%s healthcheck=%s "
        "log_format=%s log_file=%s openai=%s instance_lock=%s",
        config.environment,
        config.database_path,
        config.promo_hour_utc,
        config.promo_minute,
        config.promo_concurrency,
        config.promo_send_interval,
        "enabled" if config.promo_lock_enabled else "disabled",
        config.promo_batch_size,
        config.rate_limit,
        config.rate_limit_window,
        config.rate_limit_storage,
        healthcheck,
        config.log_format,
        config.log_file or "stdout",
        "enabled" if config.openai_api_key else "disabled",
        "enabled" if config.instance_lock_enabled else "disabled",
    )


def _warn_on_risky_config() -> None:
    if config.environment.lower() == "production" and config.log_level == "DEBUG":
        logger.warning("LOG_LEVEL=DEBUG in production environment")
    if config.environment.lower() == "production" and not config.instance_lock_enabled:
        logger.warning("INSTANCE_LOCK_ENABLED=false in production environment")
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


async def _sync_bot_profile(bot: Bot) -> None:
    if not config.bot_description and not config.bot_short_description:
        return

    if config.bot_description:
        try:
            await bot.set_my_description(config.bot_description)
            logger.info("Bot description updated")
        except Exception:
            logger.exception("Failed to update bot description")

    if config.bot_short_description:
        try:
            await bot.set_my_short_description(config.bot_short_description)
            logger.info("Bot short description updated")
        except Exception:
            logger.exception("Failed to update bot short description")


def _build_user_commands() -> list[BotCommand]:
    return [
        BotCommand(command="start", description="开始使用"),
        BotCommand(command="help", description="查看帮助"),
        BotCommand(command="submit", description="提交频道参与互推"),
        BotCommand(command="list", description="查看已通过频道"),
    ]


def _build_admin_commands() -> list[BotCommand]:
    return _build_user_commands() + [
        BotCommand(command="pending", description="查看待审核频道"),
        BotCommand(command="stats", description="查看系统统计"),
    ]


async def _sync_bot_commands(bot: Bot) -> None:
    user_commands = _build_user_commands()
    admin_commands = _build_admin_commands()

    try:
        await bot.set_my_commands(user_commands, scope=BotCommandScopeAllPrivateChats())
        await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())
        logger.info("Bot commands updated for private chats")
    except Exception:
        logger.exception("Failed to update bot commands for private chats")

    if not config.admin_ids:
        return

    for admin_id in config.admin_ids:
        try:
            await bot.set_my_commands(
                admin_commands, scope=BotCommandScopeChat(chat_id=admin_id)
            )
        except TelegramBadRequest as exc:
            if "chat not found" in str(exc).lower():
                logger.warning(
                    "Skip admin commands for %s: chat not found (admin未与机器人对话)",
                    admin_id,
                )
                continue
            logger.exception("Failed to update admin commands for %s", admin_id)
        except Exception:
            logger.exception("Failed to update admin commands for %s", admin_id)
    logger.info("Bot commands updated for admin chats")


async def _refresh_promo_lock(
    stop_event: asyncio.Event, lock_lost_event: asyncio.Event
) -> None:
    interval = max(5, config.promo_lock_ttl // 3)
    while True:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            return
        except asyncio.TimeoutError:
            refreshed = await refresh_lock(
                _PROMO_LOCK_NAME, _INSTANCE_ID, config.promo_lock_ttl
            )
            if not refreshed:
                logger.warning("Promo lock refresh failed, lock may expire")
                lock_lost_event.set()
                return


async def scheduled_promo(bot: Bot, shutdown_event: asyncio.Event | None = None):
    lock_acquired = False
    refresh_task: asyncio.Task | None = None
    stop_event: asyncio.Event | None = None
    lock_lost_event = asyncio.Event()  # Signals loss of leader lock to stop sending.
    cancel_token = (
        _CancelToken(lock_lost_event, shutdown_event)
        if shutdown_event is not None
        else lock_lost_event
    )

    try:
        if shutdown_event and shutdown_event.is_set():
            logger.info("Scheduled promo skipped: shutdown in progress")
            return
        if config.promo_lock_enabled:
            lock_acquired = await acquire_lock(
                _PROMO_LOCK_NAME, _INSTANCE_ID, config.promo_lock_ttl
            )
            if not lock_acquired:
                logger.info("Scheduled promo skipped: lock held by another instance")
                return
            stop_event = asyncio.Event()
            refresh_task = asyncio.create_task(
                _refresh_promo_lock(stop_event, lock_lost_event)
            )

        logger.info("Starting scheduled promo broadcast...")
        sent, failed = await send_promo_to_all(bot, cancel_event=cancel_token)
        logger.info(f"Promo broadcast complete: {sent} sent, {failed} failed")
    except Exception as e:
        logger.exception(f"Scheduled promo failed: {e}")
    finally:
        if stop_event is not None:
            stop_event.set()
        if refresh_task is not None:
            with contextlib.suppress(Exception):
                await refresh_task
        if lock_acquired:
            with contextlib.suppress(Exception):
                await release_lock(_PROMO_LOCK_NAME, _INSTANCE_ID)


async def main():
    _log_startup_summary()
    _warn_on_risky_config()

    instance_lock_handle = None
    if config.instance_lock_enabled:
        try:
            instance_lock_handle = acquire_instance_lock(config.instance_lock_path)
            logger.info("Instance lock acquired: %s", config.instance_lock_path)
        except InstanceLockError as exc:
            logger.error("Instance lock failed: %s", exc)
            raise SystemExit(1) from exc

    try:
        await init_db()
        logger.info("Database initialized")

        bot = Bot(token=config.bot_token)
        try:
            await _validate_bot(bot)
            await _sync_bot_profile(bot)
            await _sync_bot_commands(bot)
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
                storage=config.rate_limit_storage,
            )
        )

        dp.include_router(user_handlers.router)
        dp.include_router(admin_handlers.router)

        scheduler = AsyncIOScheduler(timezone=UTC)
        shutdown_event = asyncio.Event()
        scheduler.add_job(
            scheduled_promo,
            "cron",
            hour=config.promo_hour_utc,
            minute=config.promo_minute,
            args=[bot, shutdown_event],
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
            nonlocal shutdown_called, instance_lock_handle
            if shutdown_called:
                return
            shutdown_called = True
            logger.info("Shutting down...")
            shutdown_event.set()
            try:
                scheduler.shutdown(wait=False)
            except Exception:
                logger.exception("Scheduler shutdown failed")
            if health_server is not None:
                health_server.close()
                await health_server.wait_closed()
            with contextlib.suppress(Exception):
                await bot.session.close()
            if instance_lock_handle is not None:
                release_instance_lock(instance_lock_handle)
                instance_lock_handle = None

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
    finally:
        if instance_lock_handle is not None:
            release_instance_lock(instance_lock_handle)


if __name__ == "__main__":
    asyncio.run(main())
