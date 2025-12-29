#!/bin/bash
# SQLite 数据库恢复脚本
# 用法: ./scripts/restore_db.sh <备份文件路径>

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DB_PATH="${PROJECT_DIR}/data/bot.db"

# 检查参数
if [ -z "$1" ]; then
    echo "用法: $0 <备份文件路径>"
    echo ""
    echo "可用的备份文件:"
    ls -lh "${PROJECT_DIR}/backups"/bot_backup_*.db 2>/dev/null || echo "无备份文件"
    exit 1
fi

BACKUP_FILE="$1"

# 检查备份文件是否存在
if [ ! -f "$BACKUP_FILE" ]; then
    echo "错误: 备份文件不存在: $BACKUP_FILE"
    exit 1
fi

# 恢复前先备份当前数据库
if [ -f "$DB_PATH" ]; then
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    PRE_RESTORE="${PROJECT_DIR}/backups/pre_restore_${TIMESTAMP}.db"
    echo "备份当前数据库到: $PRE_RESTORE"
    cp "$DB_PATH" "$PRE_RESTORE"
fi

# 执行恢复
echo "从备份恢复数据库..."
cp "$BACKUP_FILE" "$DB_PATH"

echo "恢复完成: $DB_PATH"
