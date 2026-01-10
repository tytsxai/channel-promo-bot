#!/bin/sh
# Healthcheck script for /ready endpoint.

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${PROJECT_DIR}/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
fi

HOST="${HEALTHCHECK_HOST:-127.0.0.1}"
PORT="${HEALTHCHECK_PORT:-0}"
TIMEOUT="${HEALTHCHECK_TIMEOUT:-2}"

if [ -z "$PORT" ] || [ "$PORT" = "0" ]; then
    echo "Healthcheck disabled (HEALTHCHECK_PORT=0)"
    exit 0
fi

URL="http://${HOST}:${PORT}/ready"

if command -v curl >/dev/null 2>&1; then
    curl -fsS --max-time "$TIMEOUT" "$URL" >/dev/null
    exit $?
fi

python3 - "$HOST" "$PORT" "$TIMEOUT" <<'PY'
import http.client
import sys

host, port, timeout = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
conn = http.client.HTTPConnection(host, port, timeout=timeout)
try:
    conn.request("GET", "/ready")
    resp = conn.getresponse()
    if resp.status >= 500:
        raise SystemExit(1)
finally:
    conn.close()
PY
