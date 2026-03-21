#!/bin/bash
# SQLite 数据库恢复脚本
# 用法: ./scripts/restore_db.sh <备份文件路径>

set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${PROJECT_DIR}/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
fi

DB_PATH="${DATABASE_PATH:-${PROJECT_DIR}/data/bot.db}"
if [[ "$DB_PATH" != /* ]]; then
    DB_PATH="${PROJECT_DIR}/${DB_PATH}"
fi
DB_DIR="$(dirname "$DB_PATH")"
mkdir -p "$DB_DIR"

DEFAULT_LOCK_PATH="$(dirname "$DB_PATH")/bot.lock"
INSTANCE_LOCK_PATH="${INSTANCE_LOCK_PATH:-$DEFAULT_LOCK_PATH}"
if [[ "$INSTANCE_LOCK_PATH" != /* ]]; then
    INSTANCE_LOCK_PATH="${PROJECT_DIR}/${INSTANCE_LOCK_PATH}"
fi

run_integrity_check() {
    local db_file="$1"
    local result
    if command -v sqlite3 >/dev/null 2>&1; then
        result="$(sqlite3 "$db_file" "PRAGMA integrity_check;")"
    else
        if ! command -v python3 >/dev/null 2>&1; then
            echo "错误: 未找到 sqlite3 或 python3，无法校验数据库完整性" >&2
            exit 1
        fi
        result="$(python3 - "$db_file" <<'PY'
import sqlite3
import sys

path = sys.argv[1]
conn = sqlite3.connect(path)
try:
    cur = conn.execute("PRAGMA integrity_check;")
    row = cur.fetchone()
    print(row[0] if row else "no_result")
finally:
    conn.close()
PY
)"
    fi

    if [ "$result" != "ok" ]; then
        echo "错误: 数据库完整性校验失败 ($db_file): $result" >&2
        exit 1
    fi
}

assert_not_running() {
    if ! command -v python3 >/dev/null 2>&1; then
        echo "警告: 未找到 python3，跳过实例锁检查。请确认机器人已停止。" >&2
        return
    fi

    if [ "${INSTANCE_LOCK_ENABLED:-true}" = "false" ]; then
        echo "警告: INSTANCE_LOCK_ENABLED=false，无法通过实例锁判断运行状态。请确认机器人已停止。" >&2
        return
    fi

    set +e
    python3 - "$INSTANCE_LOCK_PATH" >/dev/null 2>&1 <<'PY'
import os
import sys

lock_path = sys.argv[1]
lock_dir = os.path.dirname(lock_path)
if lock_dir:
    os.makedirs(lock_dir, exist_ok=True)

try:
    import fcntl
except ImportError:
    raise SystemExit(0)

handle = open(lock_path, "a+", encoding="utf-8")
try:
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    raise SystemExit(2)
finally:
    handle.close()
PY
    rc=$?
    set -e
    if [ "$rc" -eq 2 ]; then
        echo "错误: 检测到实例锁被占用，机器人可能仍在运行。请先停机后再恢复。" >&2
        exit 1
    fi
    if [ "$rc" -ne 0 ]; then
        echo "警告: 实例锁检查异常，请确认机器人已停止。" >&2
    fi
}

snapshot_database() {
    local src_db="$1"
    local dst_db="$2"

    if command -v sqlite3 >/dev/null 2>&1; then
        sqlite3 "$src_db" ".backup '$dst_db'"
        return
    fi

    if ! command -v python3 >/dev/null 2>&1; then
        echo "错误: 未找到 sqlite3 或 python3，无法创建恢复前快照" >&2
        exit 1
    fi

    python3 - "$src_db" "$dst_db" <<'PY'
import sqlite3
import sys

src_path, dst_path = sys.argv[1:3]
src = sqlite3.connect(src_path)
dst = sqlite3.connect(dst_path)
try:
    src.backup(dst)
    dst.commit()
finally:
    dst.close()
    src.close()
PY
}

# 检查参数
if [ -z "$1" ]; then
    echo "用法: $0 <备份文件路径>"
    echo ""
    echo "可用的备份文件:"
    ls -lh "${PROJECT_DIR}/backups"/bot_backup_*.db 2>/dev/null || echo "无备份文件"
    exit 1
fi

BACKUP_FILE="$1"

if [[ "$BACKUP_FILE" != /* ]]; then
    BACKUP_FILE="$(cd "$(dirname "$BACKUP_FILE")" && pwd)/$(basename "$BACKUP_FILE")"
fi

# 检查备份文件是否存在
if [ ! -f "$BACKUP_FILE" ]; then
    echo "错误: 备份文件不存在: $BACKUP_FILE"
    exit 1
fi

echo "校验备份文件完整性..."
run_integrity_check "$BACKUP_FILE"

assert_not_running

mkdir -p "${PROJECT_DIR}/backups"

# 恢复前先备份当前数据库（使用 SQLite 在线快照，确保 WAL 一致性）
if [ -f "$DB_PATH" ]; then
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    PRE_RESTORE="${PROJECT_DIR}/backups/pre_restore_${TIMESTAMP}.db"
    echo "备份当前数据库到: $PRE_RESTORE"
    snapshot_database "$DB_PATH" "$PRE_RESTORE"
    chmod 600 "$PRE_RESTORE" 2>/dev/null || true
    echo "校验恢复前快照完整性..."
    run_integrity_check "$PRE_RESTORE"
fi

# 执行恢复
echo "从备份恢复数据库..."
TMP_RESTORE="${DB_PATH}.restore_tmp.$$"
cleanup_tmp() {
    rm -f "$TMP_RESTORE"
}
trap cleanup_tmp EXIT
cp "$BACKUP_FILE" "$TMP_RESTORE"

echo "校验恢复文件完整性..."
run_integrity_check "$TMP_RESTORE"

# SQLite WAL 模式下，恢复后必须清理旧 wal/shm，避免旧日志污染新库。
rm -f "${DB_PATH}-wal" "${DB_PATH}-shm"
mv "$TMP_RESTORE" "$DB_PATH"
rm -f "${DB_PATH}-wal" "${DB_PATH}-shm"
chmod 600 "$DB_PATH" 2>/dev/null || true
trap - EXIT

echo "恢复完成: $DB_PATH"
