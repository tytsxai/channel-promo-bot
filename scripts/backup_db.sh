#!/bin/bash
# SQLite 数据库备份脚本
# 用法: ./scripts/backup_db.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DB_PATH="${PROJECT_DIR}/data/bot.db"
BACKUP_DIR="${PROJECT_DIR}/backups"
RETENTION_DAYS=7

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
sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"

if [ -f "$BACKUP_FILE" ]; then
    echo "备份成功: $BACKUP_FILE"
    echo "文件大小: $(du -h "$BACKUP_FILE" | cut -f1)"
else
    echo "错误: 备份失败"
    exit 1
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
