import os
from dataclasses import replace

import pytest

import src.db_utils as db_utils
import src.models.database as database
import src.services.instance_lock as instance_lock
import src.services.lock_service as lock_service
from src.config import config as base_config


@pytest.fixture
def patched_db(tmp_path, monkeypatch):
    db_path = tmp_path / "data" / "bot.db"
    cfg = replace(base_config, database_path=str(db_path))
    monkeypatch.setattr(database, "config", cfg)
    monkeypatch.setattr(db_utils, "config", cfg)
    monkeypatch.setattr(lock_service, "_table_ready", False)
    return str(db_path)


@pytest.fixture
async def init_db(patched_db):
    await database.init_db()
    return patched_db


@pytest.mark.asyncio
async def test_distributed_lock_acquire_refresh_release(init_db):
    acquired = await lock_service.acquire_lock("promo", "owner-a", ttl_seconds=120)
    assert acquired is True

    blocked = await lock_service.acquire_lock("promo", "owner-b", ttl_seconds=120)
    assert blocked is False

    refreshed = await lock_service.refresh_lock("promo", "owner-a", ttl_seconds=120)
    assert refreshed is True

    await lock_service.release_lock("promo", "owner-a")

    acquired_after_release = await lock_service.acquire_lock(
        "promo", "owner-b", ttl_seconds=120
    )
    assert acquired_after_release is True


@pytest.mark.asyncio
async def test_distributed_lock_can_takeover_after_expiry(init_db, monkeypatch):
    now = {"value": 1_000.0}

    def fake_time() -> float:
        return now["value"]

    monkeypatch.setattr(lock_service.time, "time", fake_time)

    first = await lock_service.acquire_lock("promo", "owner-a", ttl_seconds=60)
    assert first is True

    now["value"] = 1_020.0
    still_blocked = await lock_service.acquire_lock("promo", "owner-b", ttl_seconds=60)
    assert still_blocked is False

    now["value"] = 1_061.0
    takeover = await lock_service.acquire_lock("promo", "owner-b", ttl_seconds=60)
    assert takeover is True


@pytest.mark.skipif(instance_lock.fcntl is None, reason="fcntl 不可用")
def test_instance_lock_exclusive_and_releasable(tmp_path):
    lock_path = tmp_path / "bot.lock"

    handle = instance_lock.acquire_instance_lock(str(lock_path))
    try:
        assert lock_path.exists()
        pid_text = lock_path.read_text(encoding="utf-8").strip()
        assert pid_text == str(os.getpid())

        with pytest.raises(instance_lock.InstanceLockError):
            instance_lock.acquire_instance_lock(str(lock_path))
    finally:
        instance_lock.release_instance_lock(handle)

    second_handle = instance_lock.acquire_instance_lock(str(lock_path))
    instance_lock.release_instance_lock(second_handle)
