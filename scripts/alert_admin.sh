#!/bin/bash
# Send a Telegram alert to admin IDs using BOT_TOKEN.
# Usage: ./scripts/alert_admin.sh "message"  (or pipe message via stdin)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${PROJECT_DIR}/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
fi

BOT_TOKEN="${BOT_TOKEN:-}"
ADMIN_IDS="${ADMIN_IDS:-}"

if [ -z "$BOT_TOKEN" ] || [ -z "$ADMIN_IDS" ]; then
    echo "缺少 BOT_TOKEN 或 ADMIN_IDS，无法发送告警" >&2
    exit 1
fi

MESSAGE="${1:-}"
if [ -z "$MESSAGE" ]; then
    if [ -t 0 ]; then
        echo "用法: $0 \"告警内容\"" >&2
        exit 1
    fi
    MESSAGE="$(cat)"
fi

send_with_curl() {
    local admin_id="$1"
    curl -fsS -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d "chat_id=${admin_id}" \
        -d "text=${MESSAGE}" \
        -d "disable_web_page_preview=1" >/dev/null
}

send_with_python() {
    local admin_id="$1"
    python3 - "$BOT_TOKEN" "$admin_id" "$MESSAGE" <<'PY'
import json
import sys
import urllib.request

token, admin_id, message = sys.argv[1], sys.argv[2], sys.argv[3]
url = f"https://api.telegram.org/bot{token}/sendMessage"
payload = json.dumps(
    {"chat_id": admin_id, "text": message, "disable_web_page_preview": True}
).encode("utf-8")
req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=5) as resp:
    if resp.status >= 400:
        raise SystemExit(1)
PY
}

IFS=',' read -r -a admin_list <<<"$ADMIN_IDS"
for admin_id in "${admin_list[@]}"; do
    admin_id="$(echo "$admin_id" | xargs)"
    if [ -z "$admin_id" ]; then
        continue
    fi
    if command -v curl >/dev/null 2>&1; then
        send_with_curl "$admin_id"
    else
        send_with_python "$admin_id"
    fi
done
