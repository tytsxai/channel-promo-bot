#!/bin/bash
# Verify alert path end-to-end and operator prerequisites.

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
ALERT_ON_CRITICAL="${ALERT_ON_CRITICAL:-true}"

if [ -z "$BOT_TOKEN" ] || [ -z "$ADMIN_IDS" ]; then
    echo "缺少 BOT_TOKEN 或 ADMIN_IDS，无法验证告警链路" >&2
    exit 1
fi

if [ "$ALERT_ON_CRITICAL" != "true" ]; then
    echo "⚠️ ALERT_ON_CRITICAL=${ALERT_ON_CRITICAL}，错误日志自动告警未启用" >&2
fi

timestamp="$(date '+%Y-%m-%d %H:%M:%S %z')"
message="✅ [AlertProbe] 告警链路自检成功 ${timestamp}"

set +e
"${PROJECT_DIR}/scripts/alert_admin.sh" "$message"
status=$?
set -e

if [ "$status" -ne 0 ]; then
    echo "告警链路校验未通过（exit=${status}）。" >&2
    echo "请确认：管理员已主动私聊机器人，且 ADMIN_IDS 配置正确。" >&2
    exit "$status"
fi

echo "告警测试消息已发送，请确认 ADMIN_IDS 中每位管理员都已收到。"
