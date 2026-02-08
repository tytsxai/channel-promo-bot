#!/bin/bash
# Production preflight checks for safe deployment.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

if [ ! -f ".env" ]; then
    echo "❌ 缺少 .env，请先复制 .env.example 并完成配置" >&2
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "❌ 缺少 .venv，请先创建虚拟环境并安装依赖" >&2
    exit 1
fi

set -a
# shellcheck disable=SC1091
. ./.env
set +a

errors=0
SKIP_TESTS="${PREFLIGHT_SKIP_TESTS:-0}"
SKIP_LINT="${PREFLIGHT_SKIP_LINT:-0}"
SKIP_BACKUP="${PREFLIGHT_SKIP_BACKUP:-0}"

check_required() {
    local name="$1"
    local value="${!name:-}"
    if [ -z "$value" ]; then
        echo "❌ 必填配置缺失: $name" >&2
        errors=$((errors + 1))
    fi
}

check_required BOT_TOKEN
check_required ADMIN_IDS

if [ "${ENVIRONMENT:-production}" = "production" ]; then
    if [ "${HEALTHCHECK_PORT:-0}" = "0" ]; then
        echo "❌ 生产环境必须启用 HEALTHCHECK_PORT" >&2
        errors=$((errors + 1))
    fi
    if [ "${INSTANCE_LOCK_ENABLED:-true}" = "false" ]; then
        echo "❌ 生产环境必须开启 INSTANCE_LOCK_ENABLED" >&2
        errors=$((errors + 1))
    fi
fi

if [ "${ALERT_ON_CRITICAL:-true}" != "true" ]; then
    echo "⚠️ 建议生产启用 ALERT_ON_CRITICAL=true" >&2
fi

if [ "${HEALTHCHECK_HOST:-127.0.0.1}" != "127.0.0.1" ] && [ "${HEALTHCHECK_HOST:-127.0.0.1}" != "localhost" ] && [ "${HEALTHCHECK_HOST:-127.0.0.1}" != "::1" ]; then
    echo "⚠️ HEALTHCHECK_HOST 非环回地址，确认未暴露到公网: ${HEALTHCHECK_HOST}" >&2
fi

if stat --version >/dev/null 2>&1; then
    env_perm=$(stat -c %a .env)
else
    env_perm=$(stat -f %Lp .env)
fi
if [ -n "$env_perm" ] && [ $((env_perm % 100)) -ne 0 ]; then
    echo "⚠️ .env 权限为 ${env_perm}，建议执行 chmod 600 .env" >&2
fi

if [ "$SKIP_TESTS" = "1" ]; then
    echo "▶ 跳过单测（PREFLIGHT_SKIP_TESTS=1）"
else
    echo "▶ 运行单测与覆盖率..."
    ./.venv/bin/python -m pytest tests/ -q
fi

if [ "$SKIP_LINT" = "1" ]; then
    echo "▶ 跳过静态检查（PREFLIGHT_SKIP_LINT=1）"
else
    echo "▶ 运行静态检查..."
    ./.venv/bin/python -m ruff check .
fi

if [ "$SKIP_BACKUP" = "1" ]; then
    echo "▶ 跳过备份链路检查（PREFLIGHT_SKIP_BACKUP=1）"
else
    echo "▶ 检查数据库备份能力..."
    if [ -n "${DATABASE_PATH:-}" ] && [ "${DATABASE_PATH}" != ":memory:" ]; then
        if [ ! -f "${DATABASE_PATH}" ] && [ ! -f "${PROJECT_DIR}/${DATABASE_PATH}" ]; then
            echo "⚠️ 数据库文件尚不存在（首次部署可忽略）: ${DATABASE_PATH}" >&2
        else
            VERIFY_BACKUP=1 ./scripts/backup_db.sh >/dev/null
            BACKUP_MAX_AGE_HOURS=1 ./scripts/check_backup_freshness.sh >/dev/null
        fi
    fi
fi

if [ -n "${BACKUP_REMOTE_HOST:-}" ] || [ -n "${BACKUP_REMOTE_DIR:-}" ]; then
    echo "▶ 检查异机备份配置..."
    if [ -z "${BACKUP_REMOTE_HOST:-}" ] || [ -z "${BACKUP_REMOTE_DIR:-}" ]; then
        echo "❌ BACKUP_REMOTE_HOST / BACKUP_REMOTE_DIR 需同时配置" >&2
        errors=$((errors + 1))
    fi
fi

if [ "$errors" -gt 0 ]; then
    echo "❌ 预检失败，共 ${errors} 项错误" >&2
    exit 1
fi

echo "✅ 预检通过，可进入发布流程"
