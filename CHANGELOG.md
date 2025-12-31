# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- 可选健康检查端点 `/health` 与 `/ready`
- 日志配置与滚动日志支持
- 简易数据库迁移机制（`PRAGMA user_version`）
- 开发依赖文件 `requirements-dev.txt` 与 ruff lint 配置

### Changed
- 配置项校验与类型处理增强
- 速率限制配置支持通过环境变量调整
- OpenAI 模型与 Base URL 可配置

### Fixed
- 输入链接解析更健壮
- 推送发送时对异常 chat_id 记录并跳过
- 并发重复提交时返回重复提示，避免误报提交成功
