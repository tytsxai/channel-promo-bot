# API 参考文档

## 概述

本文档描述了 Telegram 互推机器人的内部 API 接口，包括服务层、处理器和数据模型。

---

## 1. 配置模块 (src/config.py)

### Config 类

不可变配置数据类，从环境变量加载配置。

```python
@dataclass(frozen=True)
class Config:
    bot_token: str        # Telegram Bot Token
    admin_ids: list[int]  # 管理员用户ID列表
    bot_description: str | None      # 机器人简介（可选）
    bot_short_description: str | None # 机器人短简介（可选）
    openai_api_key: str   # OpenAI API密钥
    openai_model: str     # OpenAI 模型名称
    openai_base_url: str | None  # OpenAI API Base URL
    min_members: int      # 最低成员数要求
    database_path: str    # 数据库文件路径
    promo_hour_utc: int   # 推送小时 (UTC)
    promo_minute: int     # 推送分钟
    promo_concurrency: int  # 推送并发数
    promo_send_interval: float  # 推送间隔(秒)
    promo_lock_enabled: bool  # 是否启用分布式锁
    promo_lock_ttl: int    # 锁过期时间(秒)
    promo_batch_size: int  # 推送分页大小
    rate_limit: int       # 速率限制次数
    rate_limit_window: int  # 速率限制窗口(秒)
    rate_limit_cleanup: int # 速率记录清理间隔(秒)
    rate_limit_storage: str # 速率限制存储方式
    log_level: str        # 日志级别
    log_format: str       # 日志格式(text/json)
    log_file: str | None  # 日志文件路径
    log_max_bytes: int    # 单文件最大字节
    log_backup_count: int # 日志备份数量
    healthcheck_host: str # 健康检查地址
    healthcheck_port: int # 健康检查端口
    environment: str      # 运行环境
```

#### 方法

| 方法 | 返回类型 | 说明 |
|------|----------|------|
| `from_env()` | `Config` | 从环境变量创建配置实例 |

#### 环境变量

| 变量名 | 必填 | 默认值 | 说明 |
|--------|------|--------|------|
| `BOT_TOKEN` | 是 | - | Telegram Bot Token |
| `ADMIN_IDS` | 是 | - | 管理员ID，逗号分隔 |
| `BOT_DESCRIPTION` | 否 | - | 机器人简介（显示在资料页） |
| `BOT_SHORT_DESCRIPTION` | 否 | - | 机器人短简介 |
| `OPENAI_API_KEY` | 否 | `""` | OpenAI API密钥 |
| `OPENAI_MODEL` | 否 | `gpt-3.5-turbo` | OpenAI 模型名称 |
| `OPENAI_BASE_URL` | 否 | - | OpenAI API Base URL |
| `MIN_MEMBERS` | 否 | `700` | 最低成员数 |
| `DATABASE_PATH` | 否 | `data/bot.db` | 数据库路径 |
| `PROMO_HOUR_UTC` | 否 | `5` | 推送小时 (0-23) |
| `PROMO_MINUTE` | 否 | `0` | 推送分钟 (0-59) |
| `PROMO_CONCURRENCY` | 否 | `5` | 推送并发数 |
| `PROMO_SEND_INTERVAL` | 否 | `0.05` | 推送间隔(秒) |
| `PROMO_LOCK_ENABLED` | 否 | `true` | 是否启用分布式锁 |
| `PROMO_LOCK_TTL` | 否 | `3600` | 锁过期时间(秒) |
| `PROMO_BATCH_SIZE` | 否 | `500` | 推送分页大小 |
| `RATE_LIMIT` | 否 | `10` | 速率限制次数 |
| `RATE_LIMIT_WINDOW` | 否 | `60` | 速率限制窗口 |
| `RATE_LIMIT_CLEANUP` | 否 | `300` | 速率记录清理间隔 |
| `RATE_LIMIT_STORAGE` | 否 | `sqlite` | 速率限制存储方式 |
| `LOG_LEVEL` | 否 | `INFO` | 日志级别 |
| `LOG_FORMAT` | 否 | `text` | 日志格式 |
| `LOG_FILE` | 否 | - | 日志文件路径 |
| `LOG_MAX_BYTES` | 否 | `10485760` | 日志单文件大小 |
| `LOG_BACKUP_COUNT` | 否 | `5` | 日志备份数量 |
| `HEALTHCHECK_HOST` | 否 | `127.0.0.1` | 健康检查地址 |
| `HEALTHCHECK_PORT` | 否 | `0` | 健康检查端口(0禁用) |
| `ALERT_ON_CRITICAL` | 否 | `true` | ERROR/CRITICAL 日志触发告警 |
| `ALERT_COOLDOWN_SECONDS` | 否 | `300` | 告警冷却时间（秒） |
| `BACKUP_REMOTE_USER` | 否 | - | 异机备份 SSH 用户 |
| `BACKUP_REMOTE_HOST` | 否 | - | 异机备份目标主机 |
| `BACKUP_REMOTE_PORT` | 否 | `22` | 异机备份 SSH 端口 |
| `BACKUP_REMOTE_DIR` | 否 | - | 异机备份目标目录 |
| `ENVIRONMENT` | 否 | `production` | 运行环境 |

---

## 2. 数据库模块 (src/models/database.py)

### init_db()

初始化数据库，创建表和索引。

```python
async def init_db() -> None
```

#### 数据库表结构

**channels 表**

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INTEGER | PRIMARY KEY | 自增主键 |
| `chat_id` | TEXT | UNIQUE NOT NULL | Telegram 频道ID |
| `title` | TEXT | NOT NULL | 频道标题 |
| `username` | TEXT | - | 频道用户名 |
| `member_count` | INTEGER | DEFAULT 0 | 成员数量 |
| `category` | TEXT | - | 分类 |
| `status` | TEXT | DEFAULT 'pending' | 状态 |
| `submitted_by` | INTEGER | NOT NULL | 提交者用户ID |
| `submitted_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 提交时间 |
| `approved_at` | TIMESTAMP | - | 审核通过时间 |
| `approved_by` | INTEGER | - | 审核人ID |

**状态值 (status)**
- `pending` - 待审核
- `approved` - 已通过
- `rejected` - 已拒绝
- `inactive` - 已失效

**索引**
- `idx_channels_status` - 状态索引
- `idx_channels_category` - 分类索引

**pending_submissions 表**

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `user_id` | INTEGER | PRIMARY KEY | 提交者用户ID |
| `username` | TEXT | NOT NULL | 频道用户名 |
| `chat_id` | TEXT | - | 频道ID |
| `title` | TEXT | - | 频道标题 |
| `created_at` | REAL | NOT NULL | 提交时间戳 |

**rate_limit_requests 表**

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `user_id` | INTEGER | NOT NULL | 用户ID |
| `ts` | REAL | NOT NULL | 请求时间戳 |

**distributed_locks 表**

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `name` | TEXT | PRIMARY KEY | 锁名称 |
| `owner` | TEXT | NOT NULL | 锁持有者 |
| `expires_at` | REAL | NOT NULL | 过期时间戳 |

#### 迁移机制

通过 `PRAGMA user_version` 管理迁移版本。新增结构时在 `MIGRATIONS` 中添加迁移函数。

---

## 3. 频道服务 (src/services/channel_service.py)

### ChannelService 类

提供频道数据的 CRUD 操作。

#### 方法列表

| 方法 | 参数 | 返回类型 | 说明 |
|------|------|----------|------|
| `add_channel()` | chat_id, title, username, member_count, submitted_by | `int \| None` | 添加频道，返回ID或None |
| `get_pending_channels()` | - | `list[dict]` | 获取所有待审核频道 |
| `get_pending_channels_paginated()` | page, per_page | `tuple[list[dict], int]` | 分页获取待审核频道 |
| `approve_channel()` | channel_id, approved_by, category | `bool` | 审核通过频道 |
| `reject_channel()` | channel_id | `bool` | 拒绝频道 |
| `get_channel_by_id()` | channel_id | `dict \| None` | 根据ID获取频道 |
| `channel_exists()` | chat_id | `bool` | 检查频道是否存在 |
| `get_approved_channels()` | - | `list[dict]` | 获取所有已通过频道 |
| `mark_inactive()` | chat_id | `bool` | 标记频道为失效 |
| `get_pending_count()` | - | `int` | 获取待审核数量 |
| `get_approved_count()` | - | `int` | 获取已通过数量 |

#### 使用示例

```python
from src.services.channel_service import ChannelService

# 添加频道
channel_id = await ChannelService.add_channel(
    chat_id="-1001234567890",
    title="示例频道",
    username="example_channel",
    member_count=1500,
    submitted_by=123456789
)

# 分页获取待审核频道
channels, total = await ChannelService.get_pending_channels_paginated(
    page=0, per_page=5
)
```

---

## 4. AI 分类服务 (src/services/ai_classifier.py)

### classify_channel()

使用 OpenAI 对频道进行自动分类，可通过 `OPENAI_MODEL` 和 `OPENAI_BASE_URL` 调整模型与 API 入口。

```python
async def classify_channel(title: str, description: str = "") -> str
```

#### 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `title` | `str` | 频道标题 |
| `description` | `str` | 频道描述（可选） |

#### 返回值

返回分类名称字符串，可能的值：
- 科技数码、影视娱乐、游戏电竞、学习教育
- 资源分享、新闻资讯、生活服务、金融理财、其他

#### 错误处理

- 若 `OPENAI_API_KEY` 未配置，返回 "其他"
- API 调用失败时，返回 "其他" 并记录日志

---

## 5. 推广服务 (src/services/promo_service.py)

### send_promo_to_all()

向所有已通过审核的频道发送互推文案。

```python
async def send_promo_to_all(bot: Bot) -> tuple[int, int]
```

#### 返回值

`tuple[int, int]` - (成功发送数, 失败数)

#### 错误处理

| 异常类型 | 处理方式 |
|----------|----------|
| `TelegramRetryAfter` | 等待指定时间后重试 |
| `TelegramForbiddenError` | 标记频道为 inactive |
| `TelegramNotFound` | 标记频道为 inactive |
| `TelegramBadRequest` | 记录错误，跳过 |

---

## 6. 中间件 (src/middleware.py)

### RateLimitMiddleware

请求频率限制中间件，防止滥用。

```python
class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, limit: int = 5, window: int = 60, cleanup_interval: int = 300, storage: str = "memory")
```

#### 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `limit` | 5 | 时间窗口内最大请求数 |
| `window` | 60 | 时间窗口（秒） |
| `cleanup_interval` | 300 | 清理过期记录间隔（秒） |
| `storage` | "memory" | 速率限制存储方式（memory/sqlite） |

---

## 7. 工具函数 (src/utils.py)

### escape_markdown()

转义 Telegram MarkdownV2 特殊字符。

```python
def escape_markdown(text: str) -> str
```

#### 转义字符

`_ * [ ] ( ) ~ \` > # + = | { } . ! -`

### LineChunker

增量构建消息分片，避免超出 Telegram 消息长度限制。

```python
class LineChunker:
    def __init__(self, limit: int)
    def add_line(self, line: str) -> list[str]
    def flush(self) -> list[str]
```

### chunk_lines()

批量分片工具，适合一次性列表输出。

```python
def chunk_lines(lines: list[str], limit: int) -> list[str]
```

---

## 8. 日志配置 (src/logging_setup.py)

### JsonFormatter 类

JSON 格式日志格式化器，继承自 `logging.Formatter`。

```python
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str
```

#### 输出格式

```json
{
    "timestamp": "2024-01-01T12:00:00+00:00",
    "level": "INFO",
    "logger": "src.services.channel_service",
    "message": "Channel submitted",
    "exc_info": "..."  // 可选，仅在有异常时出现
}
```

### configure_logging()

初始化日志系统，支持文本或 JSON 格式、可选滚动日志文件输出。

```python
def configure_logging(config: Config) -> None
```

#### 功能

- 配置 stdout 流处理器
- 可选配置滚动文件处理器（RotatingFileHandler）
- 根据 `config.log_format` 选择文本或 JSON 格式
- 调用 `logging.captureWarnings(True)` 捕获 Python warnings

---

## 9. 健康检查 (src/services/health_server.py)

### start_health_server()

启动轻量 HTTP 健康检查服务。

```python
async def start_health_server(host: str, port: int) -> asyncio.AbstractServer
```

#### 端点

- `GET /health` - 进程存活检查
- `GET /ready` - 包含数据库连接检查
- `GET /metrics` - 关键计数指标快照（推送/提交）
