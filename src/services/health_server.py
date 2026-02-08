import asyncio
import contextlib
import json
import logging
from datetime import UTC, datetime

from src.config import config
from src.services.channel_service import get_db
from src.services.metrics_service import get_metrics_snapshot

logger = logging.getLogger(__name__)


async def _check_db() -> bool:
    try:
        async with get_db() as db:
            cursor = await db.execute("SELECT 1")
            row = await cursor.fetchone()
            return bool(row and row[0] == 1)
    except Exception as exc:
        logger.warning("Health check DB failed: %s", exc)
        return False


_REASONS = {
    200: "OK",
    400: "Bad Request",
    404: "Not Found",
    405: "Method Not Allowed",
    408: "Request Timeout",
    503: "Service Unavailable",
}
_MAX_REQUEST_LINE = 4096
_MAX_HEADER_BYTES = 8192
_READ_TIMEOUT_SECONDS = 5


def _json_response(status_code: int, payload: dict) -> bytes:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    reason = _REASONS.get(status_code, "OK")
    headers = [
        f"HTTP/1.1 {status_code} {reason}",
        "Content-Type: application/json; charset=utf-8",
        f"Content-Length: {len(body)}",
        "Connection: close",
        "",
        "",
    ]
    return "\r\n".join(headers).encode("utf-8") + body


async def _handle_path(path: str) -> tuple[int, dict]:
    now = datetime.now(UTC).isoformat()
    if path == "/health":
        return 200, {"status": "ok", "time": now, "environment": config.environment}

    if path == "/ready":
        db_ok = await _check_db()
        status = "ok" if db_ok else "degraded"
        code = 200 if db_ok else 503
        return code, {"status": status, "db_ok": db_ok, "time": now}

    if path == "/metrics":
        metrics = await get_metrics_snapshot()
        return 200, {"status": "ok", "time": now, "metrics": metrics}

    return 404, {"status": "not_found", "time": now}


async def _drain_headers(reader: asyncio.StreamReader) -> bool:
    total = 0
    while True:
        line = await asyncio.wait_for(reader.readline(), timeout=_READ_TIMEOUT_SECONDS)
        if not line or line in (b"\n", b"\r\n"):
            return True
        total += len(line)
        if total > _MAX_HEADER_BYTES:
            return False


async def _handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        request_line = await asyncio.wait_for(reader.readline(), timeout=5)
        if not request_line:
            return
        if len(request_line) > _MAX_REQUEST_LINE:
            writer.write(_json_response(400, {"status": "bad_request"}))
            await writer.drain()
            return
        parts = request_line.decode("utf-8", errors="ignore").strip().split()
        if len(parts) < 2:
            writer.write(_json_response(400, {"status": "bad_request"}))
            await writer.drain()
            return
        method, path = parts[0].upper(), parts[1]
        ok = await _drain_headers(reader)
        if not ok:
            writer.write(_json_response(400, {"status": "bad_request"}))
            await writer.drain()
            return
        if method != "GET":
            writer.write(_json_response(405, {"status": "method_not_allowed"}))
            await writer.drain()
            return
        status_code, payload = await _handle_path(path)
        writer.write(_json_response(status_code, payload))
        await writer.drain()
    except TimeoutError:
        writer.write(_json_response(408, {"status": "timeout"}))
        await writer.drain()
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()


async def start_health_server(host: str, port: int) -> asyncio.AbstractServer:
    server = await asyncio.start_server(_handle_client, host, port)
    sockets = server.sockets or []
    addresses = ", ".join(str(sock.getsockname()) for sock in sockets)
    logger.info("Health server listening on %s", addresses)
    return server
