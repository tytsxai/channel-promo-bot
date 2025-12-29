# 运维操作手册

本文档提供 Telegram 互推机器人的日常运维指南。

## 目录

1. [部署检查清单](#部署检查清单)
2. [日常运维](#日常运维)
3. [备份与恢复](#备份与恢复)
4. [故障排查](#故障排查)
5. [监控与告警](#监控与告警)

---

## 部署检查清单

### 上线前检查

- [ ] `.env` 文件已正确配置
- [ ] `BOT_TOKEN` 有效
- [ ] `ADMIN_IDS` 已设置
- [ ] 虚拟环境已创建并安装依赖
- [ ] 数据库目录 `data/` 存在
- [ ] 备份目录 `backups/` 存在
- [ ] 脚本有执行权限

### 验证命令

```bash
# 检查环境
./run.sh  # 应正常启动无报错

# 检查备份脚本
./scripts/backup_db.sh
ls -la backups/
```

---

## 日常运维

### 启动服务

```bash
./run.sh
```

### 后台运行 (使用 nohup)

```bash
nohup ./run.sh > logs/bot.log 2>&1 &
```

### 后台运行 (使用 systemd)

创建 `/etc/systemd/system/telegram-bot.service`:

```ini
[Unit]
Description=Telegram 互推机器人
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/互推机器儿
ExecStart=/path/to/互推机器儿/run.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用服务:

```bash
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
sudo systemctl status telegram-bot
```

---

## 备份与恢复

### 手动备份

```bash
./scripts/backup_db.sh
```

### 配置自动备份

```bash
# 编辑 crontab
crontab -e

# 添加每日凌晨 2:00 备份任务
0 2 * * * /path/to/互推机器儿/scripts/backup_db.sh >> /var/log/bot_backup.log 2>&1
```

### 恢复数据

```bash
# 查看可用备份
ls -la backups/

# 恢复指定备份
./scripts/restore_db.sh backups/bot_backup_YYYYMMDD_HHMMSS.db
```

### 备份保留策略

- 默认保留最近 7 天的备份
- 可在 `scripts/backup_db.sh` 中修改 `RETENTION_DAYS` 变量

---

## 故障排查

### 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 机器人无响应 | Token 无效 | 检查 `.env` 中的 `BOT_TOKEN` |
| 定时推送时间错误 | 时区配置 | 确认 `PROMO_HOUR_UTC` 是 UTC 时间 |
| 消息发送失败 | 特殊字符 | 检查日志中的 Markdown 错误 |
| 审核队列卡死 | 旧版本 | 更新代码，支持分页 |

### 查看日志

```bash
# 查看实时日志
tail -f logs/bot.log

# 搜索错误
grep -i error logs/bot.log
```

---

## 监控与告警

### 关键指标

- 定时推送成功率
- 消息发送失败数
- 待审核队列长度

### 健康检查

```bash
# 检查进程是否运行
pgrep -f "python main.py"

# 检查数据库文件
ls -la data/bot.db
```

### 日志关键字监控

```bash
# 监控错误日志
grep -E "(ERROR|CRITICAL)" logs/bot.log
```
