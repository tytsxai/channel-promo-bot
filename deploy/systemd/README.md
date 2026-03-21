# Systemd 部署模板

本目录提供生产环境推荐的 `systemd` 模板，覆盖：

- 主服务常驻运行
- 基础安全硬化（`NoNewPrivileges`、`ProtectSystem`、`UMask` 等）
- 每日数据库备份（含完整性校验）
- 健康检查失败告警
- 备份新鲜度检查告警

## 一键渲染与安装

在项目根目录执行：

```bash
./scripts/install_systemd_units.sh \
  --service-name channel-promo-bot \
  --run-user "$USER" \
  --app-dir "$PWD" \
  --install
```

执行后会：

1. 将模板渲染到 `deploy/systemd/generated/`
2. 复制到 `/etc/systemd/system/`
3. 自动 `daemon-reload` 并启用服务与 timers

## 仅渲染（不安装）

```bash
./scripts/install_systemd_units.sh --service-name channel-promo-bot
```

## 常用运维命令

```bash
sudo systemctl status channel-promo-bot.service --no-pager
sudo systemctl list-timers --all | grep channel-promo-bot
journalctl -u channel-promo-bot.service -f
```
