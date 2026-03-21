#!/bin/bash
# Sync latest backups to remote host/object-like directory via rsync/scp.

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
REMOTE_USER="${BACKUP_REMOTE_USER:-}"
REMOTE_HOST="${BACKUP_REMOTE_HOST:-}"
REMOTE_DIR="${BACKUP_REMOTE_DIR:-}"
SSH_PORT="${BACKUP_REMOTE_PORT:-22}"
if [[ "$BACKUP_DIR" != /* ]]; then
    BACKUP_DIR="${PROJECT_DIR}/${BACKUP_DIR}"
fi

if ! [[ "$SSH_PORT" =~ ^[0-9]+$ ]] || [ "$SSH_PORT" -lt 1 ] || [ "$SSH_PORT" -gt 65535 ]; then
    echo "BACKUP_REMOTE_PORT 必须是 1-65535 的整数: $SSH_PORT" >&2
    exit 1
fi

if [ -z "$REMOTE_HOST" ] || [ -z "$REMOTE_DIR" ]; then
    echo "缺少 BACKUP_REMOTE_HOST 或 BACKUP_REMOTE_DIR，跳过异机备份同步" >&2
    exit 1
fi

if [ ! -d "$BACKUP_DIR" ]; then
    echo "备份目录不存在: $BACKUP_DIR" >&2
    exit 1
fi

TARGET="${REMOTE_HOST}:${REMOTE_DIR}"
if [ -n "$REMOTE_USER" ]; then
    TARGET="${REMOTE_USER}@${TARGET}"
fi

if command -v rsync >/dev/null 2>&1; then
    rsync -az --delete -e "ssh -p ${SSH_PORT}" "$BACKUP_DIR/" "$TARGET/"
else
    if ! command -v scp >/dev/null 2>&1; then
        echo "未找到 rsync/scp，无法同步异机备份" >&2
        exit 1
    fi
    ssh -p "$SSH_PORT" "${REMOTE_USER:+${REMOTE_USER}@}${REMOTE_HOST}" "mkdir -p '${REMOTE_DIR}'"

    shopt -s nullglob
    backup_files=("$BACKUP_DIR"/bot_backup_*.db "$BACKUP_DIR"/pre_restore_*.db)
    shopt -u nullglob
    if [ "${#backup_files[@]}" -eq 0 ]; then
        echo "未找到可同步的备份文件" >&2
        exit 1
    fi

    scp -P "$SSH_PORT" "${backup_files[@]}" "${TARGET}/"
fi

echo "异机备份同步完成: ${TARGET}"
