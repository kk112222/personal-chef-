FROM python:3.13-slim

WORKDIR /app

# 复制所有代码
COPY . .

# 安装依赖
RUN pip install --no-cache-dir uvicorn fastapi "python-dotenv" requests && \
    pip install --no-cache-dir langchain-core langchain-openai langchain-tavily && \
    pip install --no-cache-dir langchain-chroma langchain-community langchain-text-splitters && \
    pip install --no-cache-dir langgraph-checkpoint-sqlite "alibabacloud-oss-v2>=1.3.0" dashscope

# 设置 Python 路径
ENV PYTHONPATH=/app

# 创建必要目录
RUN mkdir -p app/db app/rag/chroma_db app/static/uploads

# 暴露端口
EXPOSE 8001

# 启动
CMD uvicorn app.main:app --host 0.0.0.0 --port 8001
