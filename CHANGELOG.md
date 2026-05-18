# Changelog

All notable changes to this project will be documented in this file.

## [1.0.1] - 2026-05-19

### Added (Documentation)

- **`llms.txt`** — AI search engine index covering positioning ("production-shaped, not toy"), feature surface, explicit non-goals (no auto-approve, no Postgres/MySQL, no DM scraping), common questions.
- **README — bilingual title + keyword block** + Release / llms.txt / Issues / License nav row.
- **README — 7-question FAQ** covering Bot 加入频道权限、AI 分类可选性、SQLite 单实例锁、为什么不支持 Postgres、健康检查端口、告警 webhook 接入、MIN_MEMBERS 阈值。

### Notes

Documentation-only release on top of v1.0.0. Bot behavior, scheduler, rate limiter, health checks, and backup paths unchanged.

## [Unreleased]

### Added
- 可选健康检查端点 `/health` 与 `/ready`
- 新增锁服务与实例锁关键路径测试（防止上线后才暴露并发/互斥问题）
- 测试覆盖率新增最低门槛（`cov-fail-under=70`）
- 日志配置与滚动日志支持
- 简易数据库迁移机制（`PRAGMA user_version`）
- 开发依赖文件 `requirements-dev.txt` 与 ruff lint 配置
- 启动时 Bot Token 校验与启动配置摘要日志
- 预检脚本新增关键配置格式/范围校验（ADMIN_IDS、LOG_LEVEL、LOG_FORMAT、端口等）
- 备份脚本支持 `BACKUP_DIR` 与 `BACKUP_RETENTION_DAYS` 配置化

### Changed
- 配置项校验与类型处理增强
- 互推发送目标读取改为 keyset 分页，降低状态变更并发下的漏发风险
- 速率限制配置支持通过环境变量调整
- OpenAI 模型与 Base URL 可配置
- 测试依赖移至开发依赖，生产依赖更精简
- 健康检查请求头读取增加超时，降低慢连接占用风险
- 定时推送异常路径补齐：后台任务清理、失败计数与指标落库更稳健
- `run.sh` 与 `preflight.sh` 改为自动发现 Python 解释器（支持 `.venv*` / `PYTHON_BIN`），降低发布环境路径耦合
- systemd 主服务模板增加基础安全硬化项（`PrivateDevices`、`ProtectSystem`、`UMask` 等）
- CI 新增 `ruff` 与 shell 脚本语法检查门禁

### Fixed
- 输入链接解析更健壮
- 推送发送时对异常 chat_id 记录并跳过
- 并发重复提交时返回重复提示，避免误报提交成功
- 告警脚本 Python 回退路径改为安全临时文件，避免固定 `/tmp` 文件竞争
- 数据恢复前快照改为 SQLite 在线备份，避免 WAL 模式下直接复制主库导致回滚点不完整
- `healthcheck.sh` 的 Python 回退路径统一按 2xx 判定成功，避免将 4xx 误判为健康
- 异机备份 scp 回退路径改为失败显式报错，避免同步失败被静默吞掉
- 备份相关脚本统一处理相对 `BACKUP_DIR`，避免在非项目目录执行时路径漂移
- 备份与恢复产物权限收敛（`umask 077` + `chmod 600`），降低数据文件过宽权限风险
