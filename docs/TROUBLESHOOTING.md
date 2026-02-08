# 故障排查指南

## 1. 机器人无响应

可能原因：
- `BOT_TOKEN` 无效
- 进程未启动或被异常终止

处理步骤：
- 检查日志（若启用 `LOG_FILE`，查看日志文件）
- 验证 Bot Token 是否正确
- 使用 `systemctl status` 或 `ps` 查看进程状态

## 1.1 启动即退出

可能原因：
- `BOT_TOKEN` 无效或 Telegram 网络不可达（启动时会校验）
- 单实例锁被占用（已有实例在运行）

处理步骤：
- 确认 `.env` 中的 `BOT_TOKEN`
- 检查服务器对 Telegram 的网络连通性
- 若提示 “Instance lock failed”，说明已有实例在运行，请先停止旧进程

## 2. 提交频道失败

可能原因：
- 频道非公开或链接错误
- 机器人未加入频道
- 提交者非管理员

处理步骤：
- 确认频道链接格式正确
- 确认机器人已加入频道并具备权限
- 检查频道成员数是否达标

## 3. AI 分类失效

可能原因：
- `OPENAI_API_KEY` 未配置或无效
- OpenAI API 请求失败

处理步骤：
- 校验 `.env` 中 `OPENAI_API_KEY`
- 检查网络连通性
- 暂停 AI 分类功能（不配置 API Key 即自动降级）

## 4. 定时推送未触发

可能原因：
- 时区设置误差
- 进程异常中断

处理步骤：
- 确认 `PROMO_HOUR_UTC` / `PROMO_MINUTE`
- 检查日志中是否有定时任务输出

## 5. 健康检查失败

可能原因：
- `HEALTHCHECK_PORT` 未开启
- 数据库无法访问

处理步骤：
- 确认端口已开放并正确配置
- 访问 `/health` 和 `/ready` 端点排查具体问题

## 6. 告警未发送

可能原因：
- `ALERT_ON_CRITICAL=false`
- `scripts/alert_admin.sh` 无执行权限
- `.env` 中 `BOT_TOKEN` / `ADMIN_IDS` 缺失

处理步骤：
- 确认 `.env` 配置 `ALERT_ON_CRITICAL=true`
- 执行 `chmod +x scripts/alert_admin.sh`
- 手动测试：`./scripts/alert_admin.sh "告警链路测试"`
- 或执行完整校验：`./scripts/verify_alerting.sh`

## 7. /metrics 无数据

可能原因：
- 服务刚启动，尚未产生业务事件
- 数据库不可写导致指标入库失败

处理步骤：
- 执行一次业务流程（提交频道、触发定时推送）后再查看
- 检查日志是否有 `Failed to record promo metrics` 或 `Failed to increment metric`

## 8. 异机备份同步失败

可能原因：
- `.env` 未配置 `BACKUP_REMOTE_HOST` / `BACKUP_REMOTE_DIR`
- SSH 连通性或权限问题
- 目标目录不可写

处理步骤：
- 检查 `BACKUP_REMOTE_*` 配置是否齐全
- 测试 SSH 连接与目录权限
- 手动执行：`./scripts/sync_backup_remote.sh`
