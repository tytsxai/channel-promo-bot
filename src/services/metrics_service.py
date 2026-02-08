import asyncio
import logging
import time

from src.services.channel_service import get_db

logger = logging.getLogger(__name__)

_table_ready = False
_table_lock = asyncio.Lock()


async def _ensure_table() -> None:
    global _table_ready
    if _table_ready:
        return
    async with _table_lock:
        if _table_ready:
            return
        async with get_db() as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS metrics (
                    name TEXT PRIMARY KEY,
                    value INTEGER NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL
                )
                """
            )
            await db.commit()
        _table_ready = True


async def _upsert_metrics(values: dict[str, int]) -> None:
    if not values:
        return
    await _ensure_table()
    now = time.time()
    async with get_db() as db:
        for name, delta in values.items():
            if delta == 0:
                continue
            await db.execute(
                """
                INSERT INTO metrics (name, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    value = metrics.value + excluded.value,
                    updated_at = excluded.updated_at
                """,
                (name, delta, now),
            )
        await db.commit()


async def increment_metric(name: str, delta: int = 1) -> None:
    if not name or delta == 0:
        return
    try:
        await _upsert_metrics({name: delta})
    except Exception as exc:
        logger.warning("Failed to increment metric %s: %s", name, exc)


async def record_promo_run(
    total_targets: int,
    sent: int,
    failed: int,
    *,
    cancelled: bool,
    empty_run: bool,
) -> None:
    values = {
        "promo_run_total": 1,
        "promo_target_channels_total": max(0, total_targets),
        "promo_sent_channels_total": max(0, sent),
        "promo_failed_channels_total": max(0, failed),
        "promo_cancelled_run_total": 1 if cancelled else 0,
        "promo_empty_run_total": 1 if empty_run else 0,
    }
    try:
        await _upsert_metrics(values)
    except Exception as exc:
        logger.warning("Failed to record promo metrics: %s", exc)


async def get_metrics_snapshot() -> dict[str, int]:
    try:
        await _ensure_table()
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT name, value FROM metrics ORDER BY name"
            )
            rows = await cursor.fetchall()
            return {str(row["name"]): int(row["value"]) for row in rows}
    except Exception as exc:
        logger.warning("Failed to read metrics snapshot: %s", exc)
        return {}
