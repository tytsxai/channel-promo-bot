import pytest

import src.services.health_server as health_server


@pytest.mark.asyncio
async def test_handle_path_health():
    status, payload = await health_server._handle_path("/health")
    assert status == 200
    assert payload["status"] == "ok"


@pytest.mark.asyncio
async def test_handle_path_ready_ok(monkeypatch):
    async def fake_check_db():
        return True

    monkeypatch.setattr(health_server, "_check_db", fake_check_db)
    status, payload = await health_server._handle_path("/ready")
    assert status == 200
    assert payload["db_ok"] is True


@pytest.mark.asyncio
async def test_handle_path_ready_degraded(monkeypatch):
    async def fake_check_db():
        return False

    monkeypatch.setattr(health_server, "_check_db", fake_check_db)
    status, payload = await health_server._handle_path("/ready")
    assert status == 503
    assert payload["db_ok"] is False


@pytest.mark.asyncio
async def test_handle_path_not_found():
    status, payload = await health_server._handle_path("/unknown")
    assert status == 404
    assert payload["status"] == "not_found"


def test_json_response():
    response = health_server._json_response(200, {"status": "ok"})
    assert response.startswith(b"HTTP/1.1 200 OK")
    assert b"Content-Length" in response
