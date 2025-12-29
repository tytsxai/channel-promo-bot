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
    openai_api_key: str   # OpenAI API密钥
    min_members: int      # 最低成员数要求
    database_path: str    # 数据库文件路径
    promo_hour_utc: int   # 推送小时 (UTC)
    promo_minute: int     # 推送分钟
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
| `OPENAI_API_KEY` | 否 | `""` | OpenAI API密钥 |
| `MIN_MEMBERS` | 否 | `700` | 最低成员数 |
| `DATABASE_PATH` | 否 | `data/bot.db` | 数据库路径 |
| `PROMO_HOUR_UTC` | 否 | `5` | 推送小时 (0-23) |
| `PROMO_MINUTE` | 否 | `0` | 推送分钟 (0-59) |

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

使用 OpenAI GPT 对频道进行自动分类。

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
    def __init__(self, limit: int = 5, window: int = 60, cleanup_interval: int = 300)
```

#### 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `limit` | 5 | 时间窗口内最大请求数 |
| `window` | 60 | 时间窗口（秒） |
| `cleanup_interval` | 300 | 清理过期记录间隔（秒） |

---

## 7. 工具函数 (src/utils.py)

### escape_markdown()

转义 Telegram MarkdownV2 特殊字符。

```python
def escape_markdown(text: str) -> str
```

#### 转义字符

`_ * [ ] ( ) ~ \` > # + = | { } . ! -`
