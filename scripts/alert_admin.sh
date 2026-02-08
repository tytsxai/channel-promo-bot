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

ALERT_TIMEOUT="${ALERT_TIMEOUT:-10}"

parse_description() {
    local body="$1"
    if command -v python3 >/dev/null 2>&1; then
        python3 - "$body" <<'PY'
import json
import sys

raw = sys.argv[1]
try:
    payload = json.loads(raw)
except Exception:
    print(raw)
    raise SystemExit(0)
print(payload.get("description", raw))
PY
    else
        printf '%s' "$body"
    fi
}

is_telegram_ok() {
    local body="$1"
    if command -v python3 >/dev/null 2>&1; then
        python3 - "$body" <<'PY'
import json
import sys

raw = sys.argv[1]
try:
    payload = json.loads(raw)
except Exception:
    raise SystemExit(1)
raise SystemExit(0 if payload.get("ok") is True else 1)
PY
    else
        printf '%s' "$body" | grep -q '"ok":true'
    fi
}

send_with_curl() {
    local admin_id="$1"
    local response
    if ! response=$(curl -sS --max-time "$ALERT_TIMEOUT" -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        --data-urlencode "chat_id=${admin_id}" \
        --data-urlencode "text=${MESSAGE}" \
        -d "disable_web_page_preview=1"); then
        echo "admin ${admin_id}: 请求失败（网络异常或超时）" >&2
        return 1
    fi
    if is_telegram_ok "$response"; then
        return 0
    fi
    echo "admin ${admin_id}: $(parse_description "$response")" >&2
    return 1
}

send_with_python() {
    local admin_id="$1"
    python3 - "$BOT_TOKEN" "$admin_id" "$MESSAGE" "$ALERT_TIMEOUT" <<'PY'
import json
import sys
import urllib.request

token, admin_id, message, timeout = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
url = f"https://api.telegram.org/bot{token}/sendMessage"
payload = json.dumps(
    {"chat_id": admin_id, "text": message, "disable_web_page_preview": True}
).encode("utf-8")
req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="ignore")
except Exception as exc:
    print(f"REQUEST_ERROR: {exc}")
    raise SystemExit(2)

try:
    result = json.loads(body)
except Exception:
    print(body)
    raise SystemExit(1)

if result.get("ok") is True:
    raise SystemExit(0)

print(result.get("description", body))
raise SystemExit(1)
PY
}

IFS=',' read -r -a admin_list <<<"$ADMIN_IDS"
sent_count=0
failed_count=0
for admin_id in "${admin_list[@]}"; do
    admin_id="$(echo "$admin_id" | xargs)"
    if [ -z "$admin_id" ]; then
        continue
    fi
    if command -v curl >/dev/null 2>&1; then
        if send_with_curl "$admin_id"; then
            sent_count=$((sent_count + 1))
        else
            failed_count=$((failed_count + 1))
        fi
    else
        if send_with_python "$admin_id" >/tmp/alert_admin_py.out 2>&1; then
            sent_count=$((sent_count + 1))
        else
            failed_count=$((failed_count + 1))
            echo "admin ${admin_id}: $(cat /tmp/alert_admin_py.out)" >&2
        fi
    fi
done

if [ "$sent_count" -eq 0 ]; then
    echo "告警发送失败：未发送成功到任何管理员" >&2
    exit 1
fi

if [ "$failed_count" -gt 0 ]; then
    echo "告警部分失败：成功 ${sent_count}，失败 ${failed_count}" >&2
    exit 1
fi

echo "告警发送成功：${sent_count} 位管理员已收到"
