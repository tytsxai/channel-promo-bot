#!/bin/bash
# SQLite 数据库备份脚本
# 用法: ./scripts/backup_db.sh

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
BACKUP_DIR="${BACKUP_DIR:-${PROJECT_DIR}/backups}"
if [[ "$BACKUP_DIR" != /* ]]; then
    BACKUP_DIR="${PROJECT_DIR}/${BACKUP_DIR}"
fi
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
VERIFY_BACKUP="${VERIFY_BACKUP:-0}"

if ! [[ "$RETENTION_DAYS" =~ ^[0-9]+$ ]]; then
    echo "错误: BACKUP_RETENTION_DAYS 必须是非负整数，当前值: $RETENTION_DAYS" >&2
    exit 1
fi

# 检查 sqlite3 或 python3 是否存在
SQLITE3_AVAILABLE=1
if ! command -v sqlite3 >/dev/null 2>&1; then
    SQLITE3_AVAILABLE=0
    if ! command -v python3 >/dev/null 2>&1; then
        echo "错误: 未找到 sqlite3 或 python3，无法执行备份"
        exit 1
    fi
fi

# 检查数据库文件是否存在
if [ ! -f "$DB_PATH" ]; then
    echo "错误: 数据库文件不存在: $DB_PATH"
    exit 1
fi

# 确保备份目录存在
mkdir -p "$BACKUP_DIR"

# 生成备份文件名
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/bot_backup_${TIMESTAMP}.db"

# 执行备份
echo "开始备份数据库..."
if [ "$SQLITE3_AVAILABLE" -eq 1 ]; then
    sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"
else
    echo "未找到 sqlite3，使用 Python 备份"
    python3 - "$DB_PATH" "$BACKUP_FILE" <<'PY'
import sqlite3
import sys

db_path, backup_path = sys.argv[1:3]
src = sqlite3.connect(db_path)
dst = sqlite3.connect(backup_path)
try:
    src.backup(dst)
    dst.commit()
finally:
    dst.close()
    src.close()
PY
fi

if [ -f "$BACKUP_FILE" ]; then
    chmod 600 "$BACKUP_FILE" 2>/dev/null || true
    echo "备份成功: $BACKUP_FILE"
    echo "文件大小: $(du -h "$BACKUP_FILE" | cut -f1)"
else
    echo "错误: 备份失败"
    exit 1
fi

# 可选：备份完整性校验
if [ "$VERIFY_BACKUP" -eq 1 ]; then
    echo "执行备份完整性校验..."
    if [ "$SQLITE3_AVAILABLE" -eq 1 ]; then
        CHECK_RESULT=$(sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;")
    else
        CHECK_RESULT=$(python3 - "$BACKUP_FILE" <<'PY'
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
)
    fi
    if [ "$CHECK_RESULT" != "ok" ]; then
        echo "错误: 备份完整性校验失败: $CHECK_RESULT"
        exit 1
    fi
    echo "完整性校验通过"
fi

# 清理旧备份（保留最近 N 天）
echo "清理 ${RETENTION_DAYS} 天前的旧备份..."
find "$BACKUP_DIR" -name "bot_backup_*.db" -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true

# 显示当前备份列表
echo ""
echo "当前备份文件:"
ls -lh "$BACKUP_DIR"/bot_backup_*.db 2>/dev/null || echo "无备份文件"

echo ""
echo "备份完成!"
