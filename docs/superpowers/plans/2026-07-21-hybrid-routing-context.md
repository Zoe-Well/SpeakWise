# Hybrid Routing and Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用“显式命令 + 对话行为规则 + 高置信主题规则 + 快速模型 + 继承/兜底”的混合路由替换脆弱关键词分类，并让每次生成只构建一次无重复、可追溯、受 token 预算约束的上下文。

**Architecture:** `ConversationRouter` 只做结构化决策，`ConversationContextBuilder` 只负责历史、知识与预算；生成编排层按“读取快照 → 路由 → 构建上下文 → 保存用户消息 → 调用模型 → 保存助手消息”的顺序工作。消息表保存路由元数据，追问通过 `dialogue_act` 继承上一主题，而不是伪装成新主题。

**Tech Stack:** FastAPI, Pydantic 2, SQLModel, SQLite, OpenAI-compatible client, pytest, React, TypeScript

## Global Constraints

- `RoutingDecision` 是唯一真实路由结果，页面和 prompt 不再自行推断意图。
- 快速模型分类温度为 0，必须有短超时、严格 JSON 校验和安全 fallback。
- 当前用户消息不得同时出现在 history 和 current input。
- 历史按“轮”截取，追问、澄清、改写必须固定目标轮次。
- 所有新增数据库列可空，迁移必须幂等，兼容旧数据。
- 规则、模型和上下文选择都通过依赖注入或纯函数测试，不调用真实 API。

---

## Task 1: 定义结构化路由领域模型

**Files:**

- Create: `backend/src/models/routing.py`
- Create: `backend/tests/unit/test_routing_model.py`

- [ ] **Step 1: 写失败测试固定枚举和置信度边界**

```python
import pytest
from pydantic import ValidationError
from backend.src.models.routing import RoutingDecision


def test_routing_decision_accepts_complete_result():
    decision = RoutingDecision(
        domain="interview",
        topic_intent="technical",
        dialogue_act="continue",
        source="inherited",
        confidence=0.92,
        prompt_scope="technical",
        model_tier="pro",
    )
    assert decision.dialogue_act == "continue"


def test_confidence_must_be_between_zero_and_one():
    with pytest.raises(ValidationError):
        RoutingDecision(domain="general", topic_intent="general", dialogue_act="new_question",
                        source="fallback", confidence=1.5, model_tier="fast")
```

- [ ] **Step 2: 运行并确认模块不存在**

Run: `uv run pytest backend/tests/unit/test_routing_model.py -q`

Expected: import failure。

- [ ] **Step 3: 实现模型**

使用 `Literal` 或字符串枚举固定：

- `domain`: `interview | general`
- `topic_intent`: `self_intro | scenario | technical | career | general`
- `dialogue_act`: `new_question | continue | clarify | rewrite | ask_interviewer_followup`
- `source`: `explicit_command | rule | fast_llm | inherited | fallback | user_override`
- `model_tier`: `fast | pro`

`prompt_scope` 可空，`confidence` 使用 `Field(ge=0, le=1)`。

- [ ] **Step 4: 验证并提交**

Run: `uv run pytest backend/tests/unit/test_routing_model.py -q`

Expected: `2 passed`。

```powershell
git add backend/src/models/routing.py backend/tests/unit/test_routing_model.py
git commit -m "feat: define structured routing decision"
```

## Task 2: 实现确定性路由规则与追问继承

**Files:**

- Create: `backend/src/services/conversation_router.py`
- Create: `backend/tests/fixtures/intent_cases.json`
- Create: `backend/tests/unit/test_conversation_router_rules.py`

- [ ] **Step 1: 建立真实误判样例集**

fixture 至少包含 30 条，必须含：

```json
[
  {"text":"如何做自我介绍","topic":"self_intro","act":"new_question"},
  {"text":"我是怎么做缓存优化的","topic":"technical","act":"new_question"},
  {"text":"为什么离职","topic":"career","act":"new_question"},
  {"text":"继续追问","topic":null,"act":"continue"},
  {"text":"换一种更简洁的说法","topic":null,"act":"rewrite"},
  {"text":"你刚才说的第二点是什么意思","topic":null,"act":"clarify"}
]
```

- [ ] **Step 2: 写失败测试**

测试显式命令优先、对话行为优先于主题关键词、`continue` 继承上一条助手消息的 `topic_intent`、无历史时安全 fallback。

- [ ] **Step 3: 运行并确认失败**

Run: `uv run pytest backend/tests/unit/test_conversation_router_rules.py -q`

Expected: module import failure。

- [ ] **Step 4: 实现纯规则层**

公开接口：

公开四个纯函数签名：

- `route_by_explicit_command(command: str | None) -> RoutingDecision | None`
- `detect_dialogue_act(text: str) -> tuple[str, float] | None`
- `detect_topic(text: str) -> tuple[str, float] | None`
- `inherit_from_history(act: str, history: list[MessageSnapshot]) -> RoutingDecision | None`

规则顺序不可互换：显式命令 → 对话行为 → 高置信主题。自我介绍规则匹配“请/如何/帮我 + 自我介绍”而非裸“我是”；技术规则不可用单个“为什么”触发。

- [ ] **Step 5: 跑 fixture 并给规则层设置可量化门槛**

Run: `uv run pytest backend/tests/unit/test_conversation_router_rules.py -q`

Expected: 全部通过；高置信规则不得错误吞掉 fixture 中的 ambiguous case。

- [ ] **Step 6: 提交**

```powershell
git add backend/src/services/conversation_router.py backend/tests/fixtures/intent_cases.json backend/tests/unit/test_conversation_router_rules.py
git commit -m "feat: add deterministic dialogue and topic routing"
```

## Task 3: 为模糊输入增加快速模型分类

**Files:**

- Modify: `backend/src/services/conversation_router.py`
- Modify: `backend/src/llm/client.py`
- Create: `backend/tests/unit/test_conversation_router_llm.py`

- [ ] **Step 1: 写失败测试覆盖成功、超时和非法 JSON**

注入假的 `classify_fn`：一次返回有效 JSON，一次抛 `TimeoutError`，一次返回 markdown 包裹或未知枚举。断言只有有效结果来源为 `fast_llm`，其余走 inherited/fallback。

- [ ] **Step 2: 运行并确认缺少异步总路由函数**

Run: `uv run pytest backend/tests/unit/test_conversation_router_llm.py -q`

Expected: missing `route_message`。

- [ ] **Step 3: 实现总路由接口**

总路由接口固定为 `async route_message(text: str, command: str | None, history: list[MessageSnapshot], classify_fn: ClassifyFn) -> RoutingDecision`。`ClassifyFn` 是接收 `messages: list[dict]`、`temperature: float`、`max_tokens: int` 并返回 `Awaitable[str]` 的 Protocol。

快速模型只接收当前文本、最近 2 轮的角色与路由标签，不接收完整简历/JD。使用 `asyncio.timeout(2.5)`、temperature 0、最多 120 output tokens；输出经 `RoutingDecision.model_validate_json()` 校验。不得尝试从 markdown code fence 中“猜”JSON。

- [ ] **Step 4: 在 `LLMClient` 增加可配置分类调用**

新增 `classify(messages, timeout_seconds=2.5)`，默认使用 `FAST_MODEL`；保持生成流接口不变。此为薄封装，由路由测试中的 fake 覆盖，不单独写网络测试。

- [ ] **Step 5: 验证并提交**

Run: `uv run pytest backend/tests/unit/test_conversation_router_llm.py -q`

Expected: all passed。

```powershell
git add backend/src/services/conversation_router.py backend/src/llm/client.py backend/tests/unit/test_conversation_router_llm.py
git commit -m "feat: classify ambiguous messages with fast model"
```

## Task 4: 持久化消息路由与生成状态

**Files:**

- Modify: `backend/src/models/session.py`
- Modify: `backend/src/db/connection.py`
- Modify: `backend/src/services/session_service.py`
- Modify: `backend/src/api/sessions.py`
- Create: `backend/tests/integration/test_message_routing_metadata.py`

- [ ] **Step 1: 写 SQLite 集成失败测试**

在临时数据库调用 `init_db()` 两次，保存带路由字段的消息后再读取，断言字段保留且旧式不带字段的 `add_message()` 仍可工作。

- [ ] **Step 2: 运行并确认列或参数不存在**

Run: `uv run pytest backend/tests/integration/test_message_routing_metadata.py -q`

Expected: model field/column failure。

- [ ] **Step 3: 增加可空字段和幂等迁移**

新增：`topic_intent`、`dialogue_act`、`routing_source`、`routing_confidence`、`generation_status`。默认 `generation_status="completed"` 仅用于旧的同步保存路径；流生成先写 `generating`，完成后改 `completed`，中断为 `interrupted`，错误为 `failed`。

- [ ] **Step 4: 扩展 service 与 API DTO**

在现有 `add_message` 参数末尾增加 `routing: RoutingDecision | None = None` 和 `generation_status: str | None = None`；sessions 消息列表返回这些可空字段。纯 DTO 同步并入本任务，不另写前端测试。

- [ ] **Step 5: 验证两次迁移与兼容性**

Run: `uv run pytest backend/tests/integration/test_message_routing_metadata.py -q`

Expected: all passed。

Run: `uv run pytest backend/tests -q`

Expected: all passed。

- [ ] **Step 6: 提交**

```powershell
git add backend/src/models/session.py backend/src/db/connection.py backend/src/services/session_service.py backend/src/api/sessions.py backend/tests/integration/test_message_routing_metadata.py
git commit -m "feat: persist routing metadata on messages"
```

## Task 5: 构建无重复、可固定目标轮次的上下文

**Files:**

- Create: `backend/src/services/conversation_context.py`
- Create: `backend/tests/unit/test_conversation_context.py`
- Modify: `backend/src/services/conversation_service.py`

- [ ] **Step 1: 写失败测试固定上下文不变量**

覆盖：current input 只出现一次；按 user+assistant 轮次截取；continue/clarify/rewrite 固定上一助手轮；普通新问题不固定；历史为空可工作。

```python
context = builder.build(snapshot, current="继续追问", route=continue_route)
assert context.rendered.count("继续追问") == 1
assert context.pinned_turn_id == snapshot.turns[-1].id
```

- [ ] **Step 2: 运行并确认模块不存在**

Run: `uv run pytest backend/tests/unit/test_conversation_context.py -q`

Expected: import failure。

- [ ] **Step 3: 实现快照和 builder**

公开类型与接口：

`ConversationSnapshot` 固定包含 `session_id: int`、`mode: str`、`turns: Sequence[ConversationTurn]`、`summary: str | None`；`BuiltContext` 固定包含 `messages: list[dict]`、`manifest: dict`、`pinned_turn_id: int | None`。builder 的公开签名为 `build(snapshot: ConversationSnapshot, current: str, route: RoutingDecision, knowledge: list[ContextItem]) -> BuiltContext`。

builder 不查询数据库；编排层先一次性读出 snapshot。manifest 只记录 message id、知识项 id、字符/token 估算，不记录正文。

- [ ] **Step 4: 删除旧的重复构建路径**

用 builder 取代 `_get_recent_messages()`、`_build_context()`、`_build_free_text_context()` 中的重复职责。暂时保留兼容 wrapper 时必须标注调用者，并在本阶段结束前删除。

- [ ] **Step 5: 验证并提交**

Run: `uv run pytest backend/tests/unit/test_conversation_context.py -q`

Expected: all passed。

```powershell
git add backend/src/services/conversation_context.py backend/src/services/conversation_service.py backend/tests/unit/test_conversation_context.py
git commit -m "refactor: build conversation context once"
```

## Task 6: 加入 token 预算与确定性知识选择

**Files:**

- Create: `backend/src/services/context_budget.py`
- Create: `backend/tests/unit/test_context_budget.py`
- Modify: `backend/src/services/conversation_context.py`

- [ ] **Step 1: 写预算优先级失败测试**

断言固定顺序：system/prompt → pinned turn → current input → JD core skills → relevant projects/skills → recent turns → attachments。超预算时从最低优先级裁剪，不能截断 pinned turn 或 current input。

- [ ] **Step 2: 运行并确认模块不存在**

Run: `uv run pytest backend/tests/unit/test_context_budget.py -q`

Expected: import failure。

- [ ] **Step 3: 实现预算器**

`ContextBudget` 构造参数固定为 `max_tokens: int` 与 `reserved_output_tokens: int`，公开方法固定为 `select(candidates: list[ContextItem]) -> ContextSelection`。

首版使用可重复的字符估算 `ceil(len(text) / 2)`，中文和英文统一保守处理；每个 `ContextItem` 含 `id/kind/priority/required/text`。不得在同一任务引入外部 tokenizer。

- [ ] **Step 4: 接入 builder 并输出 manifest**

manifest 包含 selected/dropped item id、estimated_tokens、budget，不含正文。所有同输入选择结果必须稳定。

- [ ] **Step 5: 验证并提交**

Run: `uv run pytest backend/tests/unit/test_context_budget.py backend/tests/unit/test_conversation_context.py -q`

Expected: all passed。

```powershell
git add backend/src/services/context_budget.py backend/src/services/conversation_context.py backend/tests/unit/test_context_budget.py
git commit -m "feat: enforce deterministic context budget"
```

## Task 7: 重排生成编排顺序并接入混合路由

**Files:**

- Modify: `backend/src/api/generate.py`
- Modify: `backend/src/services/conversation_service.py`
- Create: `backend/tests/integration/test_generate_routing_pipeline.py`

- [ ] **Step 1: 写带 fake LLM 的集成失败测试**

记录 fake 收到的 messages，验证：

1. 当前输入只出现一次。
2. “继续追问”继承上一条 technical route。
3. 普通非面试问题走 fast tier。
4. `/followup` 来源为 explicit_command、行为为 ask_interviewer_followup。
5. 保存的用户和助手消息共享 routing metadata。

- [ ] **Step 2: 运行并确认现有顺序导致重复/分类错误**

Run: `uv run pytest backend/tests/integration/test_generate_routing_pipeline.py -q`

Expected: at least current input count 或 route assertion failed。

- [ ] **Step 3: 改造生成顺序**

严格执行：读取 session/history/knowledge snapshot → `route_message()` → `builder.build()` → 保存 user message 与 route → 调模型 → 流完成后保存 assistant message。异常时更新 generation_status，不删除 partial metadata。

- [ ] **Step 4: 将路由写入 `meta` SSE 事件**

`meta` 增加 `routing` 对象，字段与 `RoutingDecision` 一致。前端可据此展示，但 prompt 选择仅由后端完成。

- [ ] **Step 5: 验证并提交**

Run: `uv run pytest backend/tests/integration/test_generate_routing_pipeline.py -q`

Expected: all passed。

Run: `uv run pytest backend/tests -q`

Expected: all passed。

```powershell
git add backend/src/api/generate.py backend/src/services/conversation_service.py backend/tests/integration/test_generate_routing_pipeline.py
git commit -m "feat: orchestrate generation with hybrid routing"
```

## Task 8: 在接近预算时维护结构化会话摘要

**Files:**

- Create: `backend/src/models/session_memory.py`
- Modify: `backend/src/db/connection.py`
- Create: `backend/src/services/session_memory_service.py`
- Modify: `backend/src/services/conversation_context.py`
- Create: `backend/tests/integration/test_session_memory.py`

- [ ] **Step 1: 写失败测试**

短会话不生成摘要；达到预算阈值后 fake summarizer 只收到被淘汰的旧轮次；摘要保存 `covered_through_message_id`；重复构建不会重复总结同一消息。

- [ ] **Step 2: 实现最小 `SessionMemory` 表和幂等迁移**

字段：`session_id` 唯一、`summary`、`covered_through_message_id`、`updated_at`。摘要正文只存本地 SQLite。

- [ ] **Step 3: 实现阈值触发逻辑**

只有估算上下文超过预算的 80% 且存在未覆盖的被淘汰轮次才调用 fast model；摘要 prompt 输出“已确认事实/用户偏好/未解决问题”，不得生成新事实。失败时继续使用无摘要上下文，不阻断回答。

- [ ] **Step 4: 验证并提交**

Run: `uv run pytest backend/tests/integration/test_session_memory.py -q`

Expected: all passed。

```powershell
git add backend/src/models/session_memory.py backend/src/db/connection.py backend/src/services/session_memory_service.py backend/src/services/conversation_context.py backend/tests/integration/test_session_memory.py
git commit -m "feat: summarize overflow conversation history"
```

## Task 9: 前端展示路由元数据

**Files:**

- Modify: `frontend/src/pages/ConversationPage.tsx`
- Modify: `frontend/src/components/MessageBubble.tsx`
- Modify: `frontend/src/lib/streamConsumer.ts`

- [ ] **Step 1: 接收 `meta.routing` 并同步 Message 类型**

这是类型和视图接线，复用阶段一已覆盖的流解析测试，不新建测试文件。

- [ ] **Step 2: 增加低干扰标签**

助手消息下方显示如“技术问题 · 追问 · Pro”标签；confidence 仅在开发诊断模式展示。旧消息无 metadata 时不显示空标签。

- [ ] **Step 3: 构建验证**

Run: `npm run build`

Workdir: `frontend`

Expected: build succeeded。

- [ ] **Step 4: 提交**

```powershell
git add frontend/src/pages/ConversationPage.tsx frontend/src/components/MessageBubble.tsx frontend/src/lib/streamConsumer.ts
git commit -m "feat: show conversation routing metadata"
```

## Task 10: 阶段二验收

- [ ] 运行 `uv run pytest backend/tests -q`，预期全绿。
- [ ] 在 `frontend` 运行 `npm test` 与 `npm run build`，预期成功。
- [ ] 对 fixture 运行离线准确率报告，明确 rule hit、fast LLM hit、fallback 数量；禁止调用真实 API 的 CI 测试。
- [ ] 本地验证“继续追问”“换一种说法”“刚才第二点什么意思”“为什么离职”“我是怎么做缓存优化的”“如何做自我介绍”。
- [ ] 检查同一输入在模型 messages 中只出现一次。
- [ ] 记录 DB 迁移前后旧会话均可读取。
- [ ] 提交验收记录：`git commit -m "docs: record routing and context verification"`。
