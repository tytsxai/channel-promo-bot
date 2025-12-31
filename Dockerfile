FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码
COPY src/ ./src/
COPY main.py .

# 创建数据目录
RUN mkdir -p data backups

# 运行
CMD ["python", "main.py"]
