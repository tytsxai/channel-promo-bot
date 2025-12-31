# Telegram 互推机器人

一个用于管理 Telegram 频道互相推广的机器人，支持频道提交、管理员审核、AI 自动分类和定时群发互推文案。

## 功能特性

- **频道提交**: 用户可提交频道参与互推
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
git clone <repository-url>
cd 频道互推机器人-channel-promo-bot

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

# 定时推送时间 (UTC时区)
PROMO_HOUR_UTC=5
PROMO_MINUTE=0

# 速率限制配置
RATE_LIMIT=10
RATE_LIMIT_WINDOW=60
RATE_LIMIT_CLEANUP=300

# 日志配置
LOG_LEVEL=INFO
LOG_FORMAT=text
# LOG_FILE=logs/bot.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5

# 健康检查（0=禁用）
HEALTHCHECK_HOST=127.0.0.1
HEALTHCHECK_PORT=0

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

> 提示：提交者需为频道管理员或创建者，机器人需加入频道并具备权限（建议设为管理员）。

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
├── .env.example            # 环境变量模板
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

当设置 `HEALTHCHECK_PORT` 为非 0 时，服务会启动一个轻量 HTTP 健康检查端点：

- `GET /health`：进程存活检查
- `GET /ready`：包含数据库连接检查

## 运维与部署文档

更多细节请参考：

- `docs/OPERATIONS.md`
- `docs/DEPLOYMENT.md`
- `docs/TROUBLESHOOTING.md`

## 许可证

MIT License
