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
- [ ] `.env` 权限已收紧（建议 600）
- [ ] 虚拟环境已创建并安装依赖
- [ ] 已安装 sqlite3 CLI（用于备份脚本）
- [ ] 数据库目录 `data/` 存在
- [ ] 备份目录 `backups/` 存在
- [ ] 脚本有执行权限
- [ ] 确认仅运行单实例（SQLite 不适合多实例并发写）
- [ ] 单实例锁已启用（`INSTANCE_LOCK_ENABLED=true`）

### 验证命令

```bash
# 检查环境
./run.sh  # 应正常启动无报错

# 检查备份脚本
./scripts/backup_db.sh
ls -la backups/

# 检查健康检查脚本
./scripts/healthcheck.sh
```

---

## 安全基线

- `.env` 权限建议设置为 `600`，避免密钥泄露
- `ADMIN_IDS` 仅配置必要管理员，避免超量授权
- `HEALTHCHECK_HOST` 建议绑定 `127.0.0.1`，不对公网暴露
- 若怀疑密钥泄露，请立即更换 Bot Token 与 OpenAI Key
- 生产环境避免 `LOG_LEVEL=DEBUG`，防止敏感信息误入日志

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
WorkingDirectory=/path/to/频道互推机器人-channel-promo-bot
ExecStart=/path/to/频道互推机器人-channel-promo-bot/run.sh
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

可选：开启备份完整性校验

```bash
VERIFY_BACKUP=1 ./scripts/backup_db.sh
```

### 配置自动备份

```bash
# 编辑 crontab
crontab -e

# 添加每日凌晨 2:00 备份任务
0 2 * * * /path/to/频道互推机器人-channel-promo-bot/scripts/backup_db.sh >> /var/log/bot_backup.log 2>&1
```

### 恢复数据

```bash
# 查看可用备份
ls -la backups/

# 恢复指定备份
./scripts/restore_db.sh backups/bot_backup_YYYYMMDD_HHMMSS.db
```

> 恢复前务必先停止机器人进程，否则可能导致数据不一致或恢复失败。

> 备份与恢复会读取 `.env` 中的 `DATABASE_PATH`，请确保配置正确。

### 备份保留策略

- 默认保留最近 7 天的备份
- 可在 `scripts/backup_db.sh` 中修改 `RETENTION_DAYS` 变量

---

## 回滚与恢复

当出现严重故障时，按以下步骤回滚：

1. 停止服务（systemd 或手动进程）
2. 回退代码到上一版本（如 git checkout 或替换发布包）
3. 如有必要，从最近一次备份恢复数据库
4. 启动服务并验证 `/health` 与 `/ready`

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

> 若未设置 `LOG_FILE`，日志仅输出到标准输出。

---

## 监控与告警

### 关键指标

- 定时推送成功率
- 消息发送失败数
- 待审核队列长度

### 最小告警集（建议）

- 进程退出或健康检查失败（/ready 返回 503）
- 连续出现 ERROR/CRITICAL 日志
- 备份任务连续失败

### 健康检查

```bash
# 启用健康检查端口后（HEALTHCHECK_PORT>0）
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/ready
```

### 日志关键字监控

```bash
# 监控错误日志
grep -E "(ERROR|CRITICAL)" logs/bot.log
```

### 自动化健康检查 + 告警（示例）

```bash
# 每 5 分钟检查一次 /ready，失败则给管理员发告警
*/5 * * * * /path/to/频道互推机器人-channel-promo-bot/scripts/healthcheck.sh || \
  /path/to/频道互推机器人-channel-promo-bot/scripts/alert_admin.sh "❌ 互推机器人 /ready 失败"
```

> `alert_admin.sh` 使用 `.env` 中的 `BOT_TOKEN` 与 `ADMIN_IDS` 发送告警。
