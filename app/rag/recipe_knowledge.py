import json
from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.tools import tool
import os
embeddings = DashScopeEmbeddings(
    model="text-embedding-v3",
    dashscope_api_key=os.getenv("DASHSCOPE_API_KEY")
)
#向量持久化、
CHROMA_PATH = "app/rag/chroma_db"
DATA_PATH = "app/rag/recipe/chinese_recipes.json"
def build_vector_store():
    """读取 JSON，构建向量库"""
    docs = []
    with open(DATA_PATH,"r",encoding="utf-8") as f:
        for i,line in enumerate(f):
            if i >=500: #先取500条
                break
            data = json.loads(line.strip().rstrip(","))
            text = f"菜名：{data['name']}\n食材：{data['ingredients']}\n做法：{data.get('description', data.get('name', ''))}"
            doc = Document(page_content=text, metadata={"name":
    data["name"], "source": data["source"]})
            docs.append(doc)
    splitter = RecursiveCharacterTextSplitter(chunk_size=400,
    chunk_overlap=50)
    chunks = splitter.split_documents(docs)
    vector_store = Chroma.from_documents(documents=chunks,
                                         embedding=embeddings,
                                         persist_directory=CHROMA_PATH)
    return vector_store
@tool
def search_recipes(query: str) -> str:
    """根据食材或菜名搜索本地菜谱库"""
    # 如果向量库不存在，自动构建
    if not os.path.exists(os.path.join(CHROMA_PATH, "chroma.sqlite3")):
        print("[RAG] 向量库不存在，自动构建中...")
        build_vector_store()
    vector_store = Chroma(
            embedding_function=embeddings,
            persist_directory=CHROMA_PATH
      )
    results = vector_store.similarity_search(query,k=3)
    return "\n".join(r.page_content for r in results)
