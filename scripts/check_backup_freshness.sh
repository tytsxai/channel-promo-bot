#!/bin/bash
# Check latest SQLite backup age.
# Usage: ./scripts/check_backup_freshness.sh

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

BACKUP_DIR="${BACKUP_DIR:-${PROJECT_DIR}/backups}"
MAX_AGE_HOURS="${BACKUP_MAX_AGE_HOURS:-36}"
if [[ "$BACKUP_DIR" != /* ]]; then
    BACKUP_DIR="${PROJECT_DIR}/${BACKUP_DIR}"
fi

if ! [[ "$MAX_AGE_HOURS" =~ ^[0-9]+$ ]]; then
    echo "BACKUP_MAX_AGE_HOURS 必须是非负整数: $MAX_AGE_HOURS" >&2
    exit 1
fi

if [ ! -d "$BACKUP_DIR" ]; then
    echo "备份目录不存在: $BACKUP_DIR" >&2
    exit 1
fi

latest_backup=$(ls -t "$BACKUP_DIR"/bot_backup_*.db 2>/dev/null | head -n 1 || true)
if [ -z "$latest_backup" ]; then
    echo "未找到备份文件: $BACKUP_DIR/bot_backup_*.db" >&2
    exit 1
fi

if stat --version >/dev/null 2>&1; then
    latest_mtime=$(stat -c %Y "$latest_backup")
else
    latest_mtime=$(stat -f %m "$latest_backup")
fi

now=$(date +%s)
age_seconds=$((now - latest_mtime))
max_age_seconds=$((MAX_AGE_HOURS * 3600))

if [ "$age_seconds" -gt "$max_age_seconds" ]; then
    echo "备份过旧: ${latest_backup} (${age_seconds}s > ${max_age_seconds}s)" >&2
    exit 1
fi

echo "备份正常: ${latest_backup} (${age_seconds}s)"
