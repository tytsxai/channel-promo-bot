#!/bin/bash
# Render and optionally install systemd unit templates.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TEMPLATE_DIR="${PROJECT_DIR}/deploy/systemd"
GENERATED_DIR="${TEMPLATE_DIR}/generated"

SERVICE_NAME="channel-promo-bot"
RUN_USER="${USER:-root}"
APP_DIR="${PROJECT_DIR}"
DO_INSTALL=0

usage() {
    cat <<EOF
用法: $0 [选项]

选项:
  --service-name <name>  systemd 服务名 (默认: channel-promo-bot)
  --run-user <user>      运行用户 (默认: 当前用户)
  --app-dir <path>       项目路径 (默认: 当前仓库根目录)
  --install              渲染后直接安装到 /etc/systemd/system
  -h, --help             显示帮助
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --service-name)
            SERVICE_NAME="$2"
            shift 2
            ;;
        --run-user)
            RUN_USER="$2"
            shift 2
            ;;
        --app-dir)
            APP_DIR="$2"
            shift 2
            ;;
        --install)
            DO_INSTALL=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "未知参数: $1" >&2
            usage
            exit 1
            ;;
    esac
done

mkdir -p "$GENERATED_DIR"

render() {
    local src="$1"
    local dst="$2"
    sed \
        -e "s|{{SERVICE_NAME}}|${SERVICE_NAME}|g" \
        -e "s|{{RUN_USER}}|${RUN_USER}|g" \
        -e "s|{{APP_DIR}}|${APP_DIR}|g" \
        "$src" > "$dst"
}

map_file() {
    local name="$1"
    case "$name" in
        channel-promo-bot.service.tmpl)
            echo "${SERVICE_NAME}.service"
            ;;
        channel-promo-bot-backup.service.tmpl)
            echo "${SERVICE_NAME}-backup.service"
            ;;
        channel-promo-bot-backup.timer.tmpl)
            echo "${SERVICE_NAME}-backup.timer"
            ;;
        channel-promo-bot-readycheck.service.tmpl)
            echo "${SERVICE_NAME}-readycheck.service"
            ;;
        channel-promo-bot-readycheck.timer.tmpl)
            echo "${SERVICE_NAME}-readycheck.timer"
            ;;
        channel-promo-bot-backup-freshness.service.tmpl)
            echo "${SERVICE_NAME}-backup-freshness.service"
            ;;
        channel-promo-bot-backup-freshness.timer.tmpl)
            echo "${SERVICE_NAME}-backup-freshness.timer"
            ;;
        *)
            return 1
            ;;
    esac
}

rendered_files=()
for tmpl in "$TEMPLATE_DIR"/*.tmpl; do
    [ -f "$tmpl" ] || continue
    base="$(basename "$tmpl")"
    out_name="$(map_file "$base")"
    out_path="$GENERATED_DIR/$out_name"
    render "$tmpl" "$out_path"
    rendered_files+=("$out_path")
done

echo "已渲染 systemd 文件:"
printf '  - %s\n' "${rendered_files[@]}"

if [ "$DO_INSTALL" -eq 1 ]; then
    echo "安装到 /etc/systemd/system ..."
    for f in "${rendered_files[@]}"; do
        sudo cp "$f" /etc/systemd/system/
    done
    sudo systemctl daemon-reload
    sudo systemctl enable --now \
        "${SERVICE_NAME}.service" \
        "${SERVICE_NAME}-backup.timer" \
        "${SERVICE_NAME}-readycheck.timer" \
        "${SERVICE_NAME}-backup-freshness.timer"
    echo "安装并启用完成。"
fi
