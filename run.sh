#!/bin/bash
# Telegram 互推机器人启动脚本

set -e
cd "$(dirname "$0")"

# 环境检查
if [ ! -d ".venv" ]; then
    echo "错误: 虚拟环境不存在，请先运行: python3 -m venv .venv"
    exit 1
fi

if [ ! -f ".env" ]; then
    echo "错误: 配置文件 .env 不存在，请复制 .env.example 并填写配置"
    exit 1
fi

# 检查 .env 权限（避免密钥泄露）
if [ -f ".env" ]; then
    if stat --version >/dev/null 2>&1; then
        ENV_PERM=$(stat -c %a .env)
    else
        ENV_PERM=$(stat -f %Lp .env)
    fi
    if [ -n "${ENV_PERM:-}" ] && [ $((ENV_PERM % 100)) -ne 0 ]; then
        echo "警告: .env 权限为 ${ENV_PERM}，建议执行: chmod 600 .env"
    fi
fi

# 确保备份目录存在
mkdir -p backups

# 启动前执行备份（可选，取消注释启用）
# ./scripts/backup_db.sh

source .venv/bin/activate
export PYTHONUNBUFFERED=1
exec python main.py

# 定时备份配置说明:
# 添加以下 cron 任务实现每天凌晨 2:00 自动备份:
# 0 2 * * * /path/to/频道互推机器人-channel-promo-bot/scripts/backup_db.sh >> /var/log/bot_backup.log 2>&1
