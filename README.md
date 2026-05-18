# Telegram 互推机器人 · Telegram Channel Cross-Promotion Bot

[![Release](https://img.shields.io/github/v/release/tytsxai/channel-promo-bot)](https://github.com/tytsxai/channel-promo-bot/releases) · [llms.txt](llms.txt) · [Issues](https://github.com/tytsxai/channel-promo-bot/issues) · [License: MIT](LICENSE)

> **关键词**:Telegram 互推机器人 · Telegram 频道互推 bot · Telegram 频道引流 · Telegram 频道交换流量 · AI 频道分类 · Python Telegram bot 生产部署 · systemd Telegram bot · SQLite 单实例锁 · 互推文案定时群发
>
> **Keywords**: Telegram channel cross-promotion bot · Telegram cross-promo bot · channel exchange bot · Telegram channel growth automation · production-ready Python Telegram bot · systemd Telegram bot deployment · SQLite single-instance lock · AI channel classification

一个用于管理 Telegram 频道互相推广的机器人,支持频道提交、管理员审核、AI 自动分类和定时群发互推文案。**面向生产部署**:单实例锁防 SQLite 并发写损坏、分布式锁防多实例重复推送、健康检查 + 指标端点、systemd 部署模板、备份脚本、告警 hook。

## 功能特性

- **频道提交**: 用户可直接发送链接或转发消息提交频道
- **管理员审核**: 支持分页浏览和一键审核
- **AI 分类**: 使用 OpenAI 自动对频道进行分类
- **定时推送**: 每日定时向所有参与频道发送互推文案
- **速率限制**: 防止滥用的请求频率控制
- **健康检查**: 可选 HTTP 健康检查端点
- **日志与运维**: 支持日志级别配置和滚动日志

## 快速开始

### 环境要求

- Python 3.11+（建议 3.11/3.12）
- SQLite 3

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/tytsxai/channel-promo-bot.git
cd channel-promo-bot

# 2. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# (可选) 安装开发依赖
pip install -r requirements-dev.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填写必要配置
```

### 配置说明

编辑 `.env` 文件：

```bash
# Telegram Bot Token (从 @BotFather 获取)
BOT_TOKEN=your_bot_token_here

# 管理员用户ID列表 (逗号分隔)
ADMIN_IDS=123456789,987654321

# 机器人简介（显示在机器人资料页，可选）
# BOT_DESCRIPTION=
# BOT_SHORT_DESCRIPTION=

# OpenAI API Key (用于AI分类，可选)
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-3.5-turbo
# OPENAI_BASE_URL=https://api.openai.com/v1

# 最低成员数要求
MIN_MEMBERS=700

# 数据库路径
DATABASE_PATH=data/bot.db

# 单实例锁（强制单实例运行，避免 SQLite 并发写风险）
INSTANCE_LOCK_ENABLED=true
# INSTANCE_LOCK_PATH=data/bot.lock

# 定时推送时间 (UTC时区)
PROMO_HOUR_UTC=5
PROMO_MINUTE=0
# 定时推送并发与节流配置
PROMO_CONCURRENCY=5
PROMO_SEND_INTERVAL=0.05
# 多实例下使用数据库分布式锁避免重复推送
PROMO_LOCK_ENABLED=true
PROMO_LOCK_TTL=3600
# 推送读取分页大小
PROMO_BATCH_SIZE=500
# 关闭服务时等待推送任务结束的最大时间(秒)，0 表示不等待
PROMO_SHUTDOWN_TIMEOUT=30

# 速率限制配置
RATE_LIMIT=10
RATE_LIMIT_WINDOW=60
RATE_LIMIT_CLEANUP=300
# 速率限制存储方式 (memory | sqlite)
RATE_LIMIT_STORAGE=sqlite

# 日志配置
LOG_LEVEL=INFO
LOG_FORMAT=text
# LOG_FILE=logs/bot.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5

# 健康检查（生产环境必须启用；非生产可设置为 0 禁用）
HEALTHCHECK_HOST=127.0.0.1
HEALTHCHECK_PORT=8080
# HEALTHCHECK_TIMEOUT=2

# 错误日志自动告警（调用 scripts/alert_admin.sh）
ALERT_ON_CRITICAL=true
# 告警冷却时间（秒）
ALERT_COOLDOWN_SECONDS=300

# 可选：异机备份同步
# BACKUP_REMOTE_USER=backup
# BACKUP_REMOTE_HOST=192.168.1.10
# BACKUP_REMOTE_PORT=22
# BACKUP_REMOTE_DIR=/data/channel-promo-bot-backups

# 可选：备份目录与保留策略
# BACKUP_DIR=backups
# BACKUP_RETENTION_DAYS=7

# 运行环境
ENVIRONMENT=production
```

### 运行机器人

```bash
# 直接运行
./run.sh

# 或手动运行
source .venv/bin/activate
python main.py
```

`run.sh` 会按顺序自动查找解释器：`PYTHON_BIN` → 当前激活虚拟环境 → `.venv` → `.venv*` → `python3`。

## 机器人头像（可选）

仓库内置了一个示例头像：`docs/assets/bot_avatar.jpg`。你可以在 BotFather 中使用 `/setuserpic` 为机器人设置头像，
也可以替换该文件为你自己的图片（建议正方形尺寸，清晰度更好）。

![Bot Avatar](docs/assets/bot_avatar.jpg)

## 命令列表

### 用户命令

| 命令 | 说明 |
|------|------|
| `/start` | 开始使用机器人 |
| `/help` | 查看帮助信息 |
| `/submit <频道链接>` | 提交频道参与互推 |
| `/list` | 查看已通过审核的频道列表 |

> 提示：推荐直接发送频道链接（如 `t.me/yourchannel`）或转发频道消息，无需使用命令。提交者需为频道管理员或创建者，机器人需加入频道并具备权限（建议设为管理员）。

### 管理员命令

| 命令 | 说明 |
|------|------|
| `/pending` | 查看待审核频道（支持分页） |
| `/stats` | 查看系统统计信息 |

## 项目结构

```
├── main.py                 # 应用入口
├── run.sh                  # 启动脚本
├── requirements.txt        # 依赖列表
├── pyproject.toml          # 项目元数据与构建配置
├── .env.example            # 环境变量模板
├── CONTRIBUTING.md         # 贡献指南
├── CODE_OF_CONDUCT.md      # 行为准则
├── src/
│   ├── config.py           # 配置管理
│   ├── middleware.py       # 速率限制中间件
│   ├── utils.py            # 工具函数
│   ├── handlers/           # 消息处理器
│   │   ├── user_handlers.py
│   │   └── admin_handlers.py
│   ├── services/           # 业务逻辑
│   │   ├── channel_service.py
│   │   ├── promo_service.py
│   │   └── ai_classifier.py
│   └── models/
│       └── database.py     # 数据库初始化
├── scripts/
│   ├── backup_db.sh        # 数据库备份脚本
│   └── restore_db.sh       # 数据库恢复脚本
├── data/
│   └── bot.db              # SQLite 数据库
├── backups/                # 备份文件目录
└── tests/                  # 测试文件
```

## 数据备份与恢复

### 手动备份

```bash
./scripts/backup_db.sh
```

可选：启用备份完整性校验

```bash
VERIFY_BACKUP=1 ./scripts/backup_db.sh
```

### 自动备份 (cron)

```bash
# 每天凌晨 2:00 自动备份
0 2 * * * /path/to/scripts/backup_db.sh >> /var/log/bot_backup.log 2>&1
```

### 恢复数据

```bash
./scripts/restore_db.sh backups/bot_backup_20241229_020000.db
```

## 测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行测试并查看覆盖率
python -m pytest tests/ -v --cov=src

# 运行 lint
python -m ruff check .
```

## 健康检查

生产环境必须启用健康检查（`HEALTHCHECK_PORT` 需为非 0），服务会启动一个轻量 HTTP 健康检查端点：

- `GET /health`：进程存活检查
- `GET /ready`：包含数据库连接检查
- `GET /metrics`：关键计数指标（推送/提交）

你可以使用脚本快速检测：

```bash
./scripts/healthcheck.sh
```

检查指标端点：

```bash
HEALTHCHECK_ENDPOINT=metrics ./scripts/healthcheck.sh
```

## 上线前预检

发布前建议执行预检脚本（会检查关键配置、测试、lint、备份链路）：

```bash
./scripts/preflight.sh
```

可按需跳过部分步骤（例如 CI 中）：

```bash
PREFLIGHT_SKIP_TESTS=1 PREFLIGHT_SKIP_LINT=1 ./scripts/preflight.sh
```

如需指定解释器（例如非标准虚拟环境目录）：

```bash
PYTHON_BIN=.venv312/bin/python ./scripts/preflight.sh
```

## 推荐生产部署（systemd）

已提供模板与安装脚本：

```bash
./scripts/install_systemd_units.sh \
  --service-name channel-promo-bot \
  --run-user "$USER" \
  --app-dir "$PWD" \
  --install
```

模板说明见：`deploy/systemd/README.md`

## 告警与异机备份自检

```bash
# 发送一条测试告警给管理员
./scripts/verify_alerting.sh

# 执行异机备份同步（需先配置 BACKUP_REMOTE_*）
./scripts/sync_backup_remote.sh
```

## 运维与部署文档

更多细节请参考：

- `docs/OPERATIONS.md`
- `docs/DEPLOYMENT.md`
- `docs/TROUBLESHOOTING.md`

## ❓ FAQ

**Q:Bot 加进频道后还是收不到提交?**
提交者必须是频道**创建者或管理员**;机器人必须**已加入该频道并有权限**(推荐设为管理员)。两个条件缺一即失败。

**Q:AI 分类是必需的吗?**
不是。不设置 `OPENAI_API_KEY` 时分类降级为人工标记,审核流程不受影响。

**Q:如何防止多实例同时跑导致 SQLite 出问题?**
默认 `INSTANCE_LOCK_ENABLED=true` —— bot 进程启动时拿文件锁。另外 `PROMO_LOCK_ENABLED=true` 用数据库锁防止多实例重复推送。

**Q:能不能换 Postgres / MySQL?**
当前**有意只用 SQLite**(单机 + 单实例锁 + 备份脚本)。要换库需要自己改 `src/models/database.py`。

**Q:健康检查端口能关吗?**
生产环境必须开。非生产环境可以 `HEALTHCHECK_PORT=0` 关掉。

**Q:告警怎么接钉钉 / 飞书 / Slack / 企微?**
改 `scripts/alert_admin.sh`,从 `stdin` 读告警 payload 然后 curl 到你的 webhook 即可。

**Q:每个频道至少要多少人?**
默认 700(`MIN_MEMBERS` 配)。低于这个数会自动拒绝,不进入审核队列。

## 许可证

MIT License
