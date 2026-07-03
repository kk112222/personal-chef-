FROM python:3.13-slim

WORKDIR /app

# 复制项目文件
COPY . .

# 安装依赖
RUN pip install --no-cache-dir uvicorn fastapi python-dotenv requests langchain-core langchain-openai langchain-tavily langchain-chroma langchain-community langchain-text-splitters langgraph-checkpoint-sqlite alibabacloud-oss-v2 dashscope

# 设置 Python 路径，让 from app.xxx 能导入
ENV PYTHONPATH=/app:$PYTHONPATH

# 创建必要目录
RUN mkdir -p app/db app/rag/chroma_db app/static/uploads

# 暴露端口
EXPOSE 8001

# 启动
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
