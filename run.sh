#!/bin/bash
# Telegram 互推机器人启动脚本

set -euo pipefail
cd "$(dirname "$0")"

detect_python() {
    if [ -n "${PYTHON_BIN:-}" ] && [ -x "${PYTHON_BIN}" ]; then
        echo "${PYTHON_BIN}"
        return 0
    fi

    if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "${VIRTUAL_ENV}/bin/python" ]; then
        echo "${VIRTUAL_ENV}/bin/python"
        return 0
    fi

    if [ -x ".venv/bin/python" ]; then
        echo ".venv/bin/python"
        return 0
    fi

    for candidate in .venv*/bin/python; do
        if [ -x "${candidate}" ]; then
            echo "${candidate}"
            return 0
        fi
    done

    if command -v python3 >/dev/null 2>&1; then
        command -v python3
        return 0
    fi

    return 1
}

if [ ! -f ".env" ]; then
    echo "错误: 配置文件 .env 不存在，请复制 .env.example 并填写配置"
    exit 1
fi

PYTHON_BIN="$(detect_python || true)"
if [ -z "${PYTHON_BIN}" ]; then
    echo "错误: 未找到可用 Python 解释器（可设置 PYTHON_BIN）"
    exit 1
fi
echo "使用 Python: ${PYTHON_BIN} ($("${PYTHON_BIN}" -V 2>&1))"

# 检查 .env 权限（避免密钥泄露）
if stat --version >/dev/null 2>&1; then
    ENV_PERM=$(stat -c %a .env)
else
    ENV_PERM=$(stat -f %Lp .env)
fi
if [ -n "${ENV_PERM:-}" ] && [ $((ENV_PERM % 100)) -ne 0 ]; then
    echo "警告: .env 权限为 ${ENV_PERM}，建议执行: chmod 600 .env"
fi

# 确保备份目录存在
mkdir -p backups

export PYTHONUNBUFFERED=1
exec "${PYTHON_BIN}" main.py
