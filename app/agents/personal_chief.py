from app.common.logger import logger
from langchain_tavily import TavilySearch
from langchain_openai import ChatOpenAI
import os
#1加载环境变量
from dotenv import load_dotenv
import sqlite3
from app.rag.recipe_knowledge import search_recipes
load_dotenv()
from langchain.messages import HumanMessage, AIMessageChunk,AIMessage
from langgraph.graph import StateGraph, MessagesState, END
from langgraph.checkpoint.sqlite import SqliteSaver
#2 web搜索工具，使用tavily
web_search = TavilySearch(
    max_results=6,
    topic='general'
)
#多模态模型（通义千问VL通过OpenAI兼容接口调用）
model = ChatOpenAI(
    model='qwen-vl-max',
    base_url=os.getenv("DASHSCOPE_BASE_URL"),
    api_key=os.getenv("DASHSCOPE_API_KEY")
)

#记忆化
connection = sqlite3.connect(r"D:\pycharm\aiagent1\app\db\personal_chief.db",check_same_thread=False)
checkpointer = SqliteSaver(connection)
checkpointer.setup()

#4agent系统提示词
system_prompt = """
你是一名专业的私人厨师。当用户提供食材照片或食材清单后，请严格按照以下流程为用户提供服务：

1.  **识别和评估食材**：
    - 如果用户提供照片：首先识别照片中所有可见食材，根据食材的外观状态（新鲜度、成熟度、可用量）进行评估，整理出一份「当前可用食材清单」。
    - 如果用户直接提供食材清单：先确认清单内的所有食材，若有模糊不清或可能存在歧义的食材，可礼貌向用户确认。

2.  **智能食谱检索**：
    优先调用 web_search 工具，以「可用食材清单」为核心关键词，搭配“家常菜/快手菜/营养食谱”等补充关键词，查找可直接使用这些食材制作的可行菜谱。

3.  **多维度评估与排序**：
    对检索到的候选食谱，从以下两个维度进行量化打分（满分10分），并按总分从高到低排序：
    - 制作难度：越简单易操作、步骤越少、厨具要求越低，分数越高。
    - 营养价值：越均衡、越健康、食材利用率越高，分数越高。
    优先推荐制作简单且营养丰富的食谱。

4.  **结构化方案输出**：
    将排序后的食谱整理为一份清晰的建议报告，内容必须包含：
    - 食谱名称
    - 综合得分（含制作难度、营养价值分项得分）
    - 推荐理由（说明适配用户食材的原因、亮点）
    - 核心食材用量（适配用户现有食材）
    - 关键制作步骤（简明扼要，方便操作）
    - 食谱参考图片（如有，可提供图片链接或说明）

---
⚠️ 重要规则：
1.  请严格按照上述流程执行，优先调用 web_search 工具搜索食谱，搜索不到有效结果时，再根据用户食材清单合理创作食谱。
2.  所有食谱必须以用户提供的食材为核心，不主动要求用户额外采购稀有食材。
3.  输出语言保持友好、接地气，避免过于专业晦涩的术语，让用户能轻松看懂并上手。
"""

#4创建agent
class ChefState(MessagesState):
    ingredients: list[str]  # 你自定义的字段
    recipes: list[dict]
    scores: list[float]

#节点1：识别食材
def analyze_ingredients(state:ChefState):
    """调用模型识别图片/文字中的食材"""
    last_msg = state["messages"][-1]
    content = last_msg.content
    # 判断是纯文字还是图片消息
    if isinstance(content, list):  # 多模态：先让模型识别图片中的食材
        content.append({"type": "text", "text":
            "请列出图片中所有食材，用逗号分隔，不要多余文字"})
        response = model.invoke([HumanMessage(content=content)])
    else:  # 纯文字：让模型提取食材清单
        response = model.invoke([
            ("system",
             "从用户输入中提取食材清单，用逗号分隔，不要多余文字"),
            ("human", content)
        ])
    ingredients = [i.strip() for i in response.content.split(",")]
    logger.info(f"识别到食材: {ingredients}")
    # 识别结果为空，走条件分支
    if not ingredients or ingredients == [""]:
        return {"ingredients": []}
    return {"ingredients": ingredients}

# 节点2：追问食材
def clarify(state:ChefState) -> dict:
    response =model.invoke([("system", "你是私厨助手。用户没提供清楚食材信息，请礼貌地问用户具体有什么食材。"),
                            ("human", state["messages"][-1].content)])
    logger.info("食材不清晰，追问用户")
    return {"messages": [AIMessage(content=response.content)]}

# 路由函数
def should_retrieve_or_clarify(state:ChefState) -> str:
    if not state.get("ingredients") or len(state["ingredients"]) == 0:
        return "clarify"
    return "retrieve"



# 节点3：检索食谱
def retrieve_recipes(state: ChefState) -> dict:
    """根据食材搜索 web + RAG"""
    ingredients = state["ingredients"]
    query = f"用{",".join(ingredients)}可以做的家常菜谱"
    logger.info(f"搜索食谱：{query}")
    #1.搜网页
    web_results = web_search.invoke(query)
    # Tavily 返回的是字符串列表，每个字符串是一条搜索结果
    if isinstance(web_results, str):
        web_results = [web_results]
    #2.搜本地食谱
    local_result = search_recipes.invoke(query)
    #3.合并结果
    recipes = []
    for i,r in enumerate(web_results):
        recipes.append({"title":f"网页食谱{i+1}",
                        "content":r,
                        "url":""})
    if local_result:
        recipes.append({"title":"本地食谱推荐",
                        "content":local_result,
                        "url":""})
    logger.info(f"搜索到 {len(recipes)}个食谱(网页{len(web_results)} + 本地)")
    return {"recipes": recipes}
# 节点4：评分输出
def score_and_output(state: ChefState) -> dict:
    """评分排序，生成最终回答"""
    ingredients_str = ",".join(state["ingredients"])
    recipes_str = "\n".join([
        f"- {r['title']}: {r['content'][:200]}"
        for r in state["recipes"]
    ])
    response = model.invoke([("system", system_prompt),
                             ("human",f"我先有的食材：{ingredients_str}\n\n搜索到的候选食谱；{recipes_str}\n\n请按流程排序输出")
                             ])
    logger.info("食谱推荐完成")
    return {"messages": [AIMessage(content=response.content)]}
    # 返回 {"messages": [AIMessage(...)]}
builder = StateGraph(ChefState)
builder.add_node("clarify",clarify)
builder.add_node("analyze",analyze_ingredients)
builder.add_node("retrieve",retrieve_recipes)
builder.add_node("output",score_and_output)

builder.set_entry_point("analyze")
builder.add_conditional_edges("analyze",
                              should_retrieve_or_clarify,
                              {"clarify":"clarify","retrieve":"retrieve"})
builder.add_edge("clarify",END)
builder.add_edge("retrieve","output")
builder.add_edge("output",END)
agent = builder.compile(checkpointer=checkpointer)
#流式对话
async def stream_agent_response(prompt: str, image: str, thread_id: str):
    logger.info(f"[用户]: {prompt}, image: {image}, thread_id: {thread_id}")
    try:
        if not image or image.strip() == "":
            message = HumanMessage(content=prompt)
        else:
            message = HumanMessage(content=[
                {"type": "image", "url": image},
                {"type": "text", "text": prompt}
            ])
        for chunk, metadata in agent.stream(
                {"messages": [message]},
                {"configurable": {"thread_id": thread_id}},
                stream_mode="messages"
        ):
            if isinstance(chunk, AIMessageChunk) and chunk.content:
                yield chunk.content
    except Exception as e:
        logger.error(f"\n[错误]: {str(e)}")
        yield "信息检索失败，试试看手动输入食物列表？"

#清空回话
def clear_messages(thread_id:str):
    logger.info(f"清空历史消息，thread_id: {thread_id}")
    checkpointer.delete_thread(thread_id)

#查询历史会话
def get_messages(thread_id: str) -> list[dict[str, str]]:
    """获取历史会话"""
    logger.info(f"获取历史消息，thread_id: {thread_id}")
    try:
        checkpoint = checkpointer.get_tuple({"configurable": {"thread_id": thread_id}})
        if checkpoint is None:
            return []
        channel_values = checkpoint.checkpoint.get("channel_values", {})
        messages = channel_values.get("messages", [])
        if not messages:
            return []
        result = []
        for msg in messages:
            if not msg.content:
                continue
            if isinstance(msg, HumanMessage):
                result.append({"role": "user", "content": msg.content})
            elif isinstance(msg, (AIMessage, AIMessageChunk)):
                result.append({"role": "assistant", "content": msg.content})
        return result
    except Exception as e:
        logger.error(f"获取消息失败: {e}")
        return []
# 获取所有会话列表
def list_threads() -> list[dict]:
    """获取所有历史会话 ID 列表"""
    cursor = connection.cursor()
    cursor.execute("SELECT DISTINCT thread_id FROM checkpoints ORDER BY thread_id")
    threads = [{"thread_id": row[0]} for row in cursor.fetchall()]
    return threads