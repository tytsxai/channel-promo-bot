# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- 可选健康检查端点 `/health` 与 `/ready`
- 日志配置与滚动日志支持
- 简易数据库迁移机制（`PRAGMA user_version`）
- 开发依赖文件 `requirements-dev.txt` 与 ruff lint 配置
- 启动时 Bot Token 校验与启动配置摘要日志
- 预检脚本新增关键配置格式/范围校验（ADMIN_IDS、LOG_LEVEL、LOG_FORMAT、端口等）
- 备份脚本支持 `BACKUP_DIR` 与 `BACKUP_RETENTION_DAYS` 配置化

### Changed
- 配置项校验与类型处理增强
- 速率限制配置支持通过环境变量调整
- OpenAI 模型与 Base URL 可配置
- 测试依赖移至开发依赖，生产依赖更精简
- 健康检查请求头读取增加超时，降低慢连接占用风险
- 定时推送异常路径补齐：后台任务清理、失败计数与指标落库更稳健

### Fixed
- 输入链接解析更健壮
- 推送发送时对异常 chat_id 记录并跳过
- 并发重复提交时返回重复提示，避免误报提交成功
- 告警脚本 Python 回退路径改为安全临时文件，避免固定 `/tmp` 文件竞争
