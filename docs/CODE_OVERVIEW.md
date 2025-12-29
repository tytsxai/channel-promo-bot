# 代码概览

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    main.py (入口)                        │
│  - 初始化数据库                                          │
│  - 配置调度器                                            │
│  - 启动 Bot                                              │
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

**ai_classifier.py** - AI 分类
- OpenAI GPT-3.5 自动分类
- 单例模式管理客户端
- 优雅降级（无 API Key 返回默认值）

### 5. 中间件 (src/middleware.py)

**RateLimitMiddleware** - 速率限制
- 滑动窗口算法
- 定期清理过期记录防止内存泄漏

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
