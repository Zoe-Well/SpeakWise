# SpeakWise Agent 改造方案

## 改造原则

**不重写，只加一个 Agent 模式**。当前 Router 模式保留，新增一个"智能模式"开关——用户可以在面试模式和智能 Agent 模式之间切换。这样同一个项目里展示了两种架构层次：

- 面试模式 → Router + RAG（当前）
- 智能模式 → Agent + ReAct + Tool Calling

面试时你可以说："我在同一套代码里实现了规则路由和 LLM 决策路由两种模式，根据场景复杂度切换。"

---

## Agent 模式的核心差异

```
当前 Router 模式:
  用户 → classify_intent() → 固定Pipeline → LLM回答

Agent 模式:
  用户 → LLM(带工具定义) → Think → Tool Call → Observe → Think → Answer
                              ↑___________________________↓
                                   ReAct 循环
```

---

## 新增模块一：工具定义（3 个工具）

Agent 需要工具来与外部交互。定义 3 个 Function Calling 工具：

### 工具1：search_resume

```python
def search_resume(query: str) -> dict:
    """在用户知识库中搜索相关经历、技能和项目。
    
    Args:
        query: 搜索关键词，如 "Python FastAPI 项目" 或 "团队管理经历"
    
    Returns:
        {"skills": [...], "projects": [...], "internships": [...]}
    """
```

**和当前 `build_profile_data_for_prompt()` 的区别**：当前是无条件全量加载。Agent 版本只在需要时按需检索。LLM 决定"我需要查一下用户有没有 FastAPI 经验"，然后调这个工具。

### 工具2：evaluate_answer

```python
def evaluate_answer(text: str, criteria: list[str]) -> dict:
    """根据指定标准评估用户的面试回答。
    
    Args:
        text: 用户的回答文本
        criteria: 评估维度，如 ["结构完整性", "STAR遵循度", "数据支撑"]
    
    Returns:
        {"scores": {...}, "strengths": [...], "improvements": [...]}
    """
```

调一个便宜的模型（deepseek-chat）做评估，返回结构化评分。Agent 拿到评分后决定"需要重新生成"还是"这个版本够了"。

### 工具3：generate_variation

```python
def generate_variation(base_text: str, instruction: str) -> str:
    """根据改进指令重新生成回答。
    
    Args:
        base_text: 当前版本的回答
        instruction: 改进方向，如 "缩短到200字" 或 "增加技术细节"
    
    Returns:
        新版本的回答文本
    """
```

---

## 新增模块二：ReAct 循环

```python
async def agent_loop(user_message: str, profile_data: dict, jd_analysis: dict) -> str:
    """Agent ReAct 循环：思考→行动→观察→再思考→回答"""
    
    tools = [search_resume, evaluate_answer, generate_variation]
    messages = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": f"【用户背景】{summarize(profile_data)}\n【岗位】{summarize(jd_analysis)}\n【用户请求】{user_message}"}
    ]
    
    for _ in range(5):  # 最多5轮
        response = await llm.chat(messages, tools=tools)
        
        if response.tool_calls:
            # 执行工具，把结果追加到消息历史
            for tc in response.tool_calls:
                result = execute_tool(tc)
                messages.append({"role": "tool", "content": result})
            continue  # 回到循环开头，让 LLM 根据工具结果再思考
        
        return response.content  # 没有工具调用了，这是最终回答
    
    return "思考轮次过多，请简化你的问题"
```

---

## 新增模块三：Agent System Prompt

```python
AGENT_SYSTEM_PROMPT = """你是一个面试教练 AI Agent。你可以使用以下工具：

1. search_resume(query) - 在用户知识库中搜索经历
2. evaluate_answer(text, criteria) - 评估面试回答质量
3. generate_variation(text, instruction) - 根据反馈重新生成回答

工作流程：
- 接收用户的面试准备请求
- 如果需要了解用户背景，先调 search_resume 检索
- 生成初版回答后，可以用 evaluate_answer 自评
- 根据评分决定是否用 generate_variation 改进
- 最终输出你认可的版本，并解释你的决策过程

你的思考过程（工具调用和推理）会展示给用户，让他们看到 Agent 是如何工作的。
"""
```

---

## 新增模块四：UI 展示 Agent 思考链

当前思考面板显示 LLM 的 `reasoning_content`。Agent 模式下再增加一层：

```
┌─ 思考过程 ─────────────────────────┐
│ 🔧 调用工具: search_resume        │
│    参数: "FastAPI 微服务项目"      │
│                                    │
│ ✅ 工具返回:                       │
│    找到 2 个项目:                  │
│    - NoteChat (FastAPI+ChromaDB)  │
│    - AdCockpit (LangGraph Agent)  │
│                                    │
│ 🤔 推理: 用户有 FastAPI 经验...   │
│ 🔧 调用工具: generate_variation   │
│ ✅ 已生成优化版本                  │
└────────────────────────────────────┘
```

这比单纯显示 `reasoning_content` 更有表现力——面试官能看到 Agent 的工作过程。

---

## 实现优先级

| 优先级 | 模块 | 工作量 | 面试价值 |
|--------|------|--------|---------|
| P0 | Agent System Prompt + ReAct 循环 | 2天 | 展示 Agent 核心概念 |
| P0 | 工具1: search_resume | 0.5天 | 展示 Function Calling |
| P0 | Agent 思考链UI | 0.5天 | 展示 Agent 可视化 |
| P1 | 工具2: evaluate_answer | 1天 | 展示多 Agent/自评估 |
| P2 | 工具3: generate_variation | 0.5天 | 展示迭代优化能力 |
| P2 | 前端 Agent/普通模式切换 | 0.5天 | 展示架构对比 |

---

## LangGraph 版本（如果面试问"你能用 LangGraph 吗"）

```python
from langgraph.graph import StateGraph, END

class AgentState(TypedDict):
    messages: list
    tool_calls: list
    final_answer: str

def should_continue(state):
    if state.get("tool_calls"):
        return "execute_tools"
    return "end"

graph = StateGraph(AgentState)
graph.add_node("llm", llm_node)          # 调用LLM
graph.add_node("execute_tools", tool_node) # 执行工具
graph.add_edge("llm", "execute_tools")
graph.add_conditional_edges("execute_tools", should_continue, {
    "execute_tools": "llm",  # 工具结果 → 回到 LLM
    "end": END
})
graph.set_entry_point("llm")
agent = graph.compile()
```

这个版本的优势是：图结构显式定义了 Agent 的状态转移，比手写 while 循环更易维护和调试。
