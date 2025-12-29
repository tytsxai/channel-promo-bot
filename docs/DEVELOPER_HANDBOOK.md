# 开发者手册

## 开发环境搭建

### 系统要求

- Python 3.11+
- SQLite 3
- Git

### 安装步骤

```bash
# 1. 克隆项目
git clone <repository-url>
cd channel-promo-bot

# 2. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填写配置
```

### 环境变量说明

| 变量 | 必填 | 说明 |
|------|------|------|
| `BOT_TOKEN` | 是 | 从 @BotFather 获取 |
| `ADMIN_IDS` | 是 | 管理员ID，逗号分隔 |
| `OPENAI_API_KEY` | 否 | AI分类功能 |
| `MIN_MEMBERS` | 否 | 最低成员数，默认700 |
| `DATABASE_PATH` | 否 | 数据库路径 |
| `PROMO_HOUR_UTC` | 否 | 推送小时(UTC) |
| `PROMO_MINUTE` | 否 | 推送分钟 |

---

## 运行项目

```bash
# 使用启动脚本
./run.sh

# 或手动运行
source .venv/bin/activate
python main.py
```

---

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 带覆盖率
pytest tests/ -v --cov=src
```

---

## 数据库管理

### 备份

```bash
./scripts/backup_db.sh
```

### 恢复

```bash
./scripts/restore_db.sh backups/bot_backup_YYYYMMDD_HHMMSS.db
```

### 自动备份 (cron)

```bash
# 每天凌晨 2:00 自动备份
0 2 * * * /path/to/scripts/backup_db.sh >> /var/log/bot_backup.log 2>&1
```

---

## 代码规范

### 项目结构

- `src/handlers/` - 消息处理器
- `src/services/` - 业务逻辑
- `src/models/` - 数据模型

### 命名约定

- 文件名：小写下划线 (`user_handlers.py`)
- 类名：大驼峰 (`ChannelService`)
- 函数/变量：小写下划线 (`get_pending_channels`)

### 异步编程

项目全面使用 `async/await`，所有数据库和网络操作都是异步的。

---

## 扩展开发

### 添加新命令

1. 在 `src/handlers/` 中添加处理函数
2. 使用 `@router.message(Command("cmd"))` 装饰器
3. 在 `main.py` 中注册路由

### 添加新分类

编辑 `src/services/ai_classifier.py` 中的 `CATEGORIES` 列表。

### 修改数据库结构

1. 编辑 `src/models/database.py` 中的建表语句
2. 更新 `ChannelService` 中的相关方法
3. 备份现有数据后重新初始化

---

## 故障排查

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| Bot 无响应 | Token 错误 | 检查 BOT_TOKEN |
| 无法获取频道 | 频道非公开 | 确保频道公开 |
| AI 分类失败 | API Key 无效 | 检查 OPENAI_API_KEY |
| 推送失败 | Bot 被移除 | 检查 Bot 权限 |
