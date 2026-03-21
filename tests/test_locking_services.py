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


@pytest.mark.skipif(instance_lock.fcntl is None, reason="fcntl 不可用")
def test_release_none_is_noop():
    instance_lock.release_instance_lock(None)


@pytest.mark.skipif(instance_lock.fcntl is None, reason="fcntl 不可用")
def test_acquire_creates_dir(tmp_path):
    lock_path = tmp_path / "subdir" / "bot.lock"
    handle = instance_lock.acquire_instance_lock(str(lock_path))
    try:
        assert lock_path.parent.exists()
    finally:
        instance_lock.release_instance_lock(handle)


@pytest.mark.asyncio
async def test_lock_service_refresh_nonexistent(init_db):
    import src.services.lock_service as ls
    refreshed = await ls.refresh_lock("no_such_lock", "owner-x", ttl_seconds=60)
    assert refreshed is False


@pytest.mark.asyncio
async def test_lock_service_release_nonexistent_is_noop(init_db):
    import src.services.lock_service as ls
    # 不应抛异常
    await ls.release_lock("no_such_lock", "owner-x")


@pytest.mark.asyncio
async def test_lock_service_same_owner_can_reacquire(init_db):
    import src.services.lock_service as ls
    await ls.acquire_lock("reacq", "owner-a", ttl_seconds=120)
    ok = await ls.acquire_lock("reacq", "owner-a", ttl_seconds=120)
    assert ok is True


@pytest.mark.asyncio
async def test_metrics_increment_and_snapshot(patched_db):
    from dataclasses import replace
    import src.models.database as _db
    import src.services.metrics_service as metrics_service

    await _db.init_db()
    # 重置模块全局状态
    metrics_service._table_ready = False

    await metrics_service.increment_metric("test_counter", 1)
    await metrics_service.increment_metric("test_counter", 2)
    snapshot = await metrics_service.get_metrics_snapshot()
    assert snapshot.get("test_counter") == 3


@pytest.mark.asyncio
async def test_metrics_increment_zero_noop(patched_db):
    from dataclasses import replace
    import src.models.database as _db
    import src.services.metrics_service as metrics_service

    await _db.init_db()
    metrics_service._table_ready = False

    snapshot_before = await metrics_service.get_metrics_snapshot()
    await metrics_service.increment_metric("noop_counter", 0)
    snapshot_after = await metrics_service.get_metrics_snapshot()
    assert snapshot_before.get("noop_counter") == snapshot_after.get("noop_counter")


@pytest.mark.asyncio
async def test_metrics_empty_name_noop(patched_db):
    import src.models.database as _db
    import src.services.metrics_service as metrics_service

    await _db.init_db()
    metrics_service._table_ready = False
    # 空名称不应抛异常
    await metrics_service.increment_metric("", 5)


@pytest.mark.asyncio
async def test_record_promo_run(patched_db):
    import src.models.database as _db
    import src.services.metrics_service as metrics_service

    await _db.init_db()
    metrics_service._table_ready = False

    await metrics_service.record_promo_run(
        total_targets=10, sent=8, failed=2, cancelled=False, empty_run=False
    )
    snapshot = await metrics_service.get_metrics_snapshot()
    assert snapshot.get("promo_run_total") == 1
    assert snapshot.get("promo_sent_channels_total") == 8
    assert snapshot.get("promo_failed_channels_total") == 2


@pytest.mark.asyncio
async def test_record_promo_run_empty(patched_db):
    import src.models.database as _db
    import src.services.metrics_service as metrics_service

    await _db.init_db()
    metrics_service._table_ready = False

    await metrics_service.record_promo_run(
        total_targets=0, sent=0, failed=0, cancelled=False, empty_run=True
    )
    snapshot = await metrics_service.get_metrics_snapshot()
    assert snapshot.get("promo_empty_run_total") == 1


@pytest.mark.asyncio
async def test_metrics_snapshot_empty_db(patched_db):
    import src.models.database as _db
    import src.services.metrics_service as metrics_service

    await _db.init_db()
    metrics_service._table_ready = False

    snapshot = await metrics_service.get_metrics_snapshot()
    assert isinstance(snapshot, dict)
