FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码和必要文件
COPY src/ ./src/
COPY main.py .
COPY scripts/ ./scripts/
COPY docs/ ./docs/
COPY deploy/ ./deploy/
COPY tests/ ./tests/
COPY requirements-dev.txt .
COPY pytest.ini .
COPY run.sh .
COPY LICENSE .
COPY CHANGELOG.md .

# 创建数据目录
RUN mkdir -p data backups
RUN chmod +x /app/scripts/*.sh /app/run.sh

# 运行
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD ["/app/scripts/healthcheck.sh"]
CMD ["python", "main.py"]
