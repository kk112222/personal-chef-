# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

**私厨助手（Personal Chief）** — AI 私人厨师智能体。用户提供食材照片或清单，Agent 自动识别食材、搜索食谱、评分排序并输出结构化建议。

### 技术栈

- **Agent 框架**: LangGraph (StateGraph + checkpointer)
- **视觉模型**: 通义千问 VL (DashScope OpenAI 兼容接口)
- **Web 搜索**: Tavily
- **追踪**: LangSmith
- **后端**: FastAPI
- **图片存储**: Aliyun OSS (预签名 URL)
- **记忆**: SQLite (SqliteSaver)
- **前端**: Next.js 静态导出

## 项目结构

```
├── app/
│   ├── main.py                      # FastAPI 入口，挂载路由/CORS/静态文件
│   ├── agents/
│   │   └── personal_chief.py        # LangGraph Agent：系统提示词+多模态模型+搜索+记忆
│   ├── api/
│   │   └── v1/
│   │       ├── chat.py              # 对话流式接口 / 历史查询 / 清除
│   │       └── oss.py               # OSS 预签名上传 URL
│   ├── common/
│   │   └── logger.py                # 全局日志配置
│   ├── models/
│   │   └── schemas.py               # Pydantic 数据模型
│   └── static/                      # Next.js 前端静态文件
├── langgraph.json                   # LangGraph API 部署配置
├── pyproject.toml                   # 项目依赖
└── .env                             # 环境变量（API Keys）
```

## 关键架构说明

### Agent 调用链

```
用户输入(文字/图片) → FastAPI /chat/stream → search_recipes()
  → HumanMessage(多模态) → agent.stream() → yield AIMessageChunk
  → StreamingResponse(text/event-stream) → 前端
```

- `agent` 是一个 LangGraph `CompiledStateGraph`，通过 `create_agent()` 构建
- 支持**流式输出**（stream_mode="messages"）
- 内置**对话记忆**（SQLite checkpointer，按 thread_id 隔离会话）
- 支持**多模态输入**（文字 + 图片 URL）

### 外部服务

| 服务 | 用途 | 配置方式 |
|------|------|----------|
| DashScope | 通义千问 VL 视觉模型 | `DASHSCOPE_API_KEY` + `DASHSCOPE_BASE_URL` |
| Tavily | Web 食谱搜索 | `TAVILY_API_KEY` |
| LangSmith | Agent 调用追踪 | `LANGSMITH_API_KEY` + `LANGSMITH_TRACING=true` |
| Aliyun OSS | 用户上传图片存储 | `OSS_ACCESS_KEY_ID` / `OSS_ACCESS_KEY_SECRET` |

### 数据流

1. 前端调用 OSS presign 接口获取上传 URL → 用户上传图片
2. 前端发送流式对话请求（文字 + 图片 URL）
3. Agent 调用 Tavily 搜索食谱 → 模型分析排序 → 流式返回结果
4. 所有调用被 LangSmith 追踪

## 常用命令

```bash
# 启动 LangGraph 开发服务器（含 Studio 调试界面）
.venv/Scripts/langgraph dev

# 直接启动 FastAPI 服务（端口 8001）
.venv/Scripts/python -m app.main

# 验证 langgraph.json 配置
.venv/Scripts/langgraph-verify-graphs

# 安装/更新依赖
.venv/Scripts/pip install -e .

# 激活虚拟环境（如果尚未激活）
source .venv/Scripts/activate
```

### 访问地址

| 服务 | 地址 |
|------|------|
| LangGraph API | http://127.0.0.1:2024 |
| LangGraph API Docs | http://127.0.0.1:2024/docs |
| FastAPI 服务 | http://127.0.0.1:8001 |
| LangSmith Studio | https://smith.langchain.com/studio |

## 重要提示

- `.env` 包含阿里云/通义/Tavily/LangSmith 密钥，**不要提交到 git**
- 数据库文件保存在 `app/db/personal_chief.db`，已加入 `.gitignore`
- `langgraph.json` 中的 graph 路径不能带前导点号（`.app/` → `app/`）
- OSS 预签名 URL 有效期 1 小时，需前端在过期前完成上传
