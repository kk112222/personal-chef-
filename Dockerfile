FROM python:3.13-slim

WORKDIR /app

# 复制依赖文件并安装（先复制 pyproject 可以让 docker 缓存依赖层）
COPY pyproject.toml .
RUN pip install --no-cache-dir uvicorn fastapi python-dotenv requests langchain-core langchain-openai langchain-tavily langchain-chroma langchain-community langchain-text-splitters langgraph-checkpoint-sqlite alibabacloud-oss-v2 dashscope

# 再复制代码
COPY . .

# 创建必要目录
RUN mkdir -p app/db app/rag/chroma_db app/static/uploads

# 暴露端口
EXPOSE 8001

# 启动
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
