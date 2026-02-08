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

to_lower() {
    printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

to_upper() {
    printf '%s' "$1" | tr '[:lower:]' '[:upper:]'
}

is_false_value() {
    case "$(to_lower "$1")" in
        0|false|no|n|off)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

is_true_value() {
    case "$(to_lower "$1")" in
        1|true|yes|y|on)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

check_required BOT_TOKEN
check_required ADMIN_IDS

if [ -n "${ADMIN_IDS:-}" ] && ! printf '%s' "$ADMIN_IDS" | grep -Eq '^[0-9]+([[:space:]]*,[[:space:]]*[0-9]+)*$'; then
    echo "❌ ADMIN_IDS 格式错误，应为逗号分隔的数字列表" >&2
    errors=$((errors + 1))
fi

environment_normalized="$(to_lower "${ENVIRONMENT:-production}")"

if [ -n "${DATABASE_PATH:-}" ] && [ "${DATABASE_PATH}" = ":memory:" ] && [ "$environment_normalized" = "production" ]; then
    echo "❌ 生产环境禁止 DATABASE_PATH=:memory:" >&2
    errors=$((errors + 1))
fi

if [ -n "${PROMO_LOCK_TTL:-}" ] && ! printf '%s' "$PROMO_LOCK_TTL" | grep -Eq '^[0-9]+$'; then
    echo "❌ PROMO_LOCK_TTL 必须是整数" >&2
    errors=$((errors + 1))
fi

if [ -n "${PROMO_LOCK_TTL:-}" ] && [ "$PROMO_LOCK_TTL" -lt 60 ] 2>/dev/null; then
    echo "❌ PROMO_LOCK_TTL 建议 >= 60，当前: $PROMO_LOCK_TTL" >&2
    errors=$((errors + 1))
fi

if [ -n "${PROMO_CONCURRENCY:-}" ] && ! printf '%s' "$PROMO_CONCURRENCY" | grep -Eq '^[1-9][0-9]*$'; then
    echo "❌ PROMO_CONCURRENCY 必须是正整数" >&2
    errors=$((errors + 1))
fi

if [ -n "${PROMO_BATCH_SIZE:-}" ] && ! printf '%s' "$PROMO_BATCH_SIZE" | grep -Eq '^[1-9][0-9]*$'; then
    echo "❌ PROMO_BATCH_SIZE 必须是正整数" >&2
    errors=$((errors + 1))
fi

rate_limit_storage_normalized="$(to_lower "${RATE_LIMIT_STORAGE:-}")"
if [ -n "${RATE_LIMIT_STORAGE:-}" ] && [ "$rate_limit_storage_normalized" != "memory" ] && [ "$rate_limit_storage_normalized" != "sqlite" ]; then
    echo "❌ RATE_LIMIT_STORAGE 只能为 memory 或 sqlite" >&2
    errors=$((errors + 1))
fi

log_level_normalized="$(to_upper "${LOG_LEVEL:-}")"
if [ -n "${LOG_LEVEL:-}" ] && ! printf '%s' "$log_level_normalized" | grep -Eq '^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$'; then
    echo "❌ LOG_LEVEL 非法: ${LOG_LEVEL}" >&2
    errors=$((errors + 1))
fi

log_format_normalized="$(to_lower "${LOG_FORMAT:-}")"
if [ -n "${LOG_FORMAT:-}" ] && [ "$log_format_normalized" != "text" ] && [ "$log_format_normalized" != "json" ]; then
    echo "❌ LOG_FORMAT 只能为 text 或 json" >&2
    errors=$((errors + 1))
fi

if [ "$environment_normalized" = "production" ]; then
    if [ "${HEALTHCHECK_PORT:-0}" = "0" ]; then
        echo "❌ 生产环境必须启用 HEALTHCHECK_PORT" >&2
        errors=$((errors + 1))
    fi
    if is_false_value "${INSTANCE_LOCK_ENABLED:-true}"; then
        echo "❌ 生产环境必须开启 INSTANCE_LOCK_ENABLED" >&2
        errors=$((errors + 1))
    fi
fi

if ! is_true_value "${ALERT_ON_CRITICAL:-true}"; then
    echo "⚠️ 建议生产启用 ALERT_ON_CRITICAL=true" >&2
fi

if [ "${HEALTHCHECK_HOST:-127.0.0.1}" != "127.0.0.1" ] && [ "${HEALTHCHECK_HOST:-127.0.0.1}" != "localhost" ] && [ "${HEALTHCHECK_HOST:-127.0.0.1}" != "::1" ]; then
    echo "⚠️ HEALTHCHECK_HOST 非环回地址，确认未暴露到公网: ${HEALTHCHECK_HOST}" >&2
fi

if [ "${HEALTHCHECK_PORT:-0}" != "0" ] && [ -n "${HEALTHCHECK_PORT:-}" ]; then
    if ! printf '%s' "$HEALTHCHECK_PORT" | grep -Eq '^[0-9]+$'; then
        echo "❌ HEALTHCHECK_PORT 必须是整数" >&2
        errors=$((errors + 1))
    elif [ "$HEALTHCHECK_PORT" -lt 1 ] || [ "$HEALTHCHECK_PORT" -gt 65535 ]; then
        echo "❌ HEALTHCHECK_PORT 超出范围(1-65535): ${HEALTHCHECK_PORT}" >&2
        errors=$((errors + 1))
    fi
fi

if [ -n "${LOG_FILE:-}" ]; then
    log_dir="$(dirname "$LOG_FILE")"
    if [ -n "$log_dir" ] && [ "$log_dir" != "." ] && [ ! -d "$log_dir" ]; then
        mkdir -p "$log_dir" 2>/dev/null || true
    fi
    if ! touch "$LOG_FILE" 2>/dev/null; then
        echo "❌ LOG_FILE 不可写: ${LOG_FILE}" >&2
        errors=$((errors + 1))
    fi
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
