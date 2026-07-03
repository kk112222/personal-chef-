FROM python:3.13-slim

WORKDIR /app

# 安装uvicorn和项目依赖
COPY pyproject.toml .
RUN pip install --no-cache-dir uvicorn && pip install --no-cache-dir -e .

# 创建必要目录
RUN mkdir -p app/db app/rag/chroma_db app/static/uploads

# 复制代码
COPY . .

# 暴露端口
EXPOSE 8001

# 启动
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
