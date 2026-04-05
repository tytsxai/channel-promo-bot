# 贡献指南

感谢你对 Telegram 频道互推机器人的关注！

## 开发环境

```bash
# 1. 克隆并进入项目
git clone https://github.com/tytsxai/channel-promo-bot.git
cd channel-promo-bot

# 2. 创建虚拟环境
python3 -m venv .venv && source .venv/bin/activate

# 3. 安装开发依赖
pip install -r requirements-dev.txt

# 4. 复制配置
cp .env.example .env
```

## 工作流

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 代码规范

- 使用 [Ruff](https://github.com/astral-sh/ruff) 进行 lint：`ruff check .`
- 遵循 PEP 8 风格
- 函数保持单一职责，缩进不超过 3 层
- 新增功能需附带测试

## 测试

```bash
# 运行所有测试（覆盖率门槛 70%）
pytest tests/ -v

# 查看覆盖率详情
pytest tests/ -v --cov=src --cov-report=term-missing
```

## 提交规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

- `feat:` 新功能
- `fix:` 修复
- `docs:` 文档更新
- `refactor:` 重构
- `test:` 测试相关
- `chore:` 构建/工具链

## 问题反馈

- 使用 GitHub Issues 报告 bug 或提出功能建议
- 提供复现步骤、环境信息（Python 版本、OS）
