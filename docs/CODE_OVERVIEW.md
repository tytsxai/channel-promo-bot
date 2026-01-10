# 代码概览

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    main.py (入口)                       │
│  - 初始化数据库                                         │
│  - 配置调度器                                           │
│  - 启动 Bot                                             │
│  - 启动健康检查端点                                     │
└─────────────────────────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ Handlers │    │ Services │    │  Models  │
    │ 消息处理  │    │ 业务逻辑  │    │ 数据模型  │
    └──────────┘    └──────────┘    └──────────┘
           │               │               │
           └───────────────┼───────────────┘
                           ▼
                    ┌──────────┐
                    │ SQLite   │
                    │ Database │
                    └──────────┘
```

---

## 目录结构

```
├── main.py                 # 应用入口
├── src/
│   ├── config.py           # 配置管理
│   ├── logging_setup.py    # 日志配置
│   ├── middleware.py       # 速率限制中间件
│   ├── utils.py            # 工具函数
│   ├── handlers/           # 消息处理器
│   │   ├── user_handlers.py
│   │   └── admin_handlers.py
│   ├── services/           # 业务逻辑
│   │   ├── channel_service.py
│   │   ├── promo_service.py
│   │   ├── ai_classifier.py
│   │   └── health_server.py
│   └── models/
│       └── database.py     # 数据库初始化
├── scripts/                # 运维脚本
├── tests/                  # 测试文件
└── data/                   # 数据目录
```

---

## 核心模块说明

### 1. 入口模块 (main.py)

**职责**：应用启动和生命周期管理

**关键流程**：
1. 初始化数据库 (`init_db()`)
2. 创建 Bot 和 Dispatcher 实例
3. 注册中间件和路由
4. 配置定时任务调度器
5. 启动轮询，处理优雅关闭

### 2. 配置模块 (src/config.py)

**职责**：集中管理环境变量配置

**设计模式**：
- 使用 `@dataclass(frozen=True)` 确保配置不可变
- 工厂方法 `from_env()` 从环境变量创建实例
- 启动时验证必填配置，失败则退出

### 2.1 日志配置 (src/logging_setup.py)

**职责**：统一日志格式与输出

**核心组件**：
- `JsonFormatter` - JSON 格式日志格式化器
- `configure_logging()` - 日志系统初始化函数

**特性**：
- 支持文本与 JSON 日志格式
- 可选滚动日志文件输出（RotatingFileHandler）
- 自动捕获 Python warnings

### 3. 处理器层 (src/handlers/)

**user_handlers.py** - 用户命令处理
- `/start` - 欢迎消息
- `/help` - 帮助信息
- `/submit` - 提交频道
- `/list` - 查看频道列表

**admin_handlers.py** - 管理员命令处理
- `/pending` - 待审核列表（分页）
- `/stats` - 系统统计
- 回调处理：审核通过/拒绝

### 4. 服务层 (src/services/)

**channel_service.py** - 频道数据操作
- 异步上下文管理器管理数据库连接
- 静态方法提供 CRUD 操作

**promo_service.py** - 推广消息发送
- 构建分类分组的推广文案
- 带重试机制的消息发送
- 自动处理频道失效情况
- 推送采用分页读取与并发 worker 队列

**ai_classifier.py** - AI 分类
- OpenAI GPT-3.5 自动分类
- 单例模式管理客户端
- 优雅降级（无 API Key 返回默认值）

**health_server.py** - 健康检查
- 提供 `/health` 和 `/ready` 端点
- 启用数据库连通性检查

**lock_service.py** - 分布式锁
- 基于 SQLite 的轻量锁，用于多实例防重

**instance_lock.py** - 单实例锁
- 文件锁方式强制单实例运行

**pending_submission_service.py** - 待验证提交持久化
- 提交信息落库，重启与多实例一致性

**db_utils.py** - 数据库路径工具
- 统一处理 `:memory:` 共享内存连接

### 5. 中间件 (src/middleware.py)

**RateLimitMiddleware** - 速率限制
- 滑动窗口算法（可选内存/SQLite 后端）
- 定期清理过期记录防止内存/存储膨胀

---

## 数据流

### 频道提交流程

```
用户发送 /submit @channel
        │
        ▼
  验证频道链接格式
        │
        ▼
  调用 Telegram API 获取频道信息
        │
        ▼
  检查成员数是否达标
        │
        ▼
  检查是否重复提交
        │
        ▼
  写入数据库 (status=pending)
```

### 审核流程

```
管理员发送 /pending
        │
        ▼
  分页显示待审核频道
        │
        ▼
  点击 ✅ 通过按钮
        │
        ▼
  AI 自动分类频道
        │
        ▼
  更新状态为 approved
```

### 定时推送流程

```
APScheduler 触发定时任务
        │
        ▼
  获取所有 approved 频道
        │
        ▼
  构建分类分组的推广文案
        │
        ▼
  遍历频道发送消息（带重试）
        │
        ▼
  处理失效频道（标记 inactive）

### 运行时健康检查

```
健康检查端口启动 (可选)
        │
        ▼
GET /health /ready
        │
        ▼
返回 JSON 状态与数据库连通性
```

---

## 技术栈

| 组件 | 技术 | 版本 |
|------|------|------|
| 框架 | aiogram | 3.4.1 |
| 数据库 | SQLite + aiosqlite | 0.19.0 |
| 调度器 | APScheduler | 3.10.4 |
| AI | OpenAI API | 1.6.1 |
| HTTP | httpx | 0.26.0 |
| 环境变量 | python-dotenv | 1.0.0 |
