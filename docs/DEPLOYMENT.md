# 部署指南

本指南用于将 Telegram 互推机器人部署到生产环境。

## 1. 运行前准备

- 准备 Python 3.11+ 环境（建议 3.11/3.12）
- 创建 `.env` 并填写配置（参见 `.env.example`）
- 确保 `data/` 与 `backups/` 目录可写
- 如需健康检查，设置 `HEALTHCHECK_PORT` 为非 0
- 生产环境建议使用密钥管理服务注入环境变量，不要提交 `.env`

## 2. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. 启动服务

```bash
./run.sh
```

数据库迁移会在启动时自动执行（基于 `PRAGMA user_version`）。

## 4. Systemd 部署示例

创建 `/etc/systemd/system/telegram-bot.service`:

```ini
[Unit]
Description=Telegram 互推机器人
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/频道互推机器人-channel-promo-bot
EnvironmentFile=/path/to/频道互推机器人-channel-promo-bot/.env
ExecStart=/path/to/频道互推机器人-channel-promo-bot/run.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动与查看状态：

```bash
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
sudo systemctl status telegram-bot
```

## 5. 健康检查与监控

启用 `HEALTHCHECK_PORT` 后：

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/ready
```

## 6. 日志与备份

- 推荐设置 `LOG_FILE=logs/bot.log` 进行日志落盘
- 使用 `scripts/backup_db.sh` 定期备份数据库

## 7. 回滚策略

建议至少保留上一版本的代码包或 Git tag。一旦出现问题：

1. 停止服务
2. 回退代码到上一版本
3. 如需数据回滚，使用最近备份恢复数据库
4. 重启服务并验证健康检查
