# SpeakWise 对话体验强化设计

**日期**：2026-07-21

**状态**：已确认，待实施计划

**范围**：强化现有对话、简历评审、追问和上下文能力，不引入新的 Agent 框架

## 1. 背景

SpeakWise 已具备 SSE 流式生成、Markdown 渲染、面试意图分类、会话历史、知识库注入、简历评审和显式 `/followup`。实际页面测试确认存在以下产品问题：

1. 对话与简历评审的流式正文会混入字面量 `data:`，生成中 Markdown 排版与完成后不一致。
2. 当前意图分类完全由关键词规则完成，并非“LLM 决策 + 关键词兜底”。宽泛关键词及两套不一致分类器会造成误判。
3. 只有显式 `/followup` 进入追问分支；自然语言追问进入通用问答，虽然生成模型可能根据历史理解用户意图，但行为不稳定。
4. 不同路由使用不同历史策略；通用面试分支会重复注入近期历史及当前问题。
5. 简历评审可能生成没有知识库依据的联系方式、量化指标和技术经历。

本设计采用“混合路由升级”方案，在修复现有链路的基础上增加低置信度 LLM 分类、主题与对话行为双维路由、统一上下文构建和评审事实约束。

## 2. 目标

- 保证前端累计流式正文与后端最终正文一致。
- 生成中和完成后使用同一 Markdown 渲染规则。
- 统一普通模式与面试模式的路由决策。
- 稳定识别自然语言追问、改写、澄清和请求面试官追问。
- 让当前问题和历史消息在 Prompt 中各出现一次。
- 对长对话实行可解释的轮次选择和预算裁剪。
- 防止简历评审把建议或占位信息冒充用户事实。
- 为错误恢复、用户纠错和自动化回归提供统一接口。

## 3. 非目标

- 不引入 LangGraph、Multi-Agent 或自主工具调用。
- 不增加向量数据库或语义检索服务。
- 不更换现有模型供应商体系。
- 不重构现有页面信息架构。
- 不进行模型微调或上传用户纠错数据。
- 不在本次设计中实现 SaaS 多租户改造。

## 4. 总体架构

新增或收敛为以下职责单元：

1. `SSEDecoder`：规范解析所有 SSE 端点。
2. `StreamAccumulator`：统一 token、thinking、完成、中止和失败状态。
3. `MarkdownRenderer`：流式和完成态使用同一解析树。
4. `ConversationRouter`：产生唯一的 `RoutingDecision`。
5. `ConversationContextBuilder`：构建唯一的 LLM 上下文。
6. `TokenBudgetManager`：按优先级控制输入预算。
7. `ReviewEvidenceBuilder`：构建简历评审证据包。
8. `ReviewClaimValidator`：检查评审中的无依据事实。

生成器只接收标准化的路由、上下文、知识和模板输入，不再自行分类或查询历史。

## 5. 流式协议与渲染

### 5.1 SSE 载荷

所有事件使用 JSON 数据载荷：

```text
event: token
data: {"seq":12,"text":"## 标题\n"}

event: thinking
data: {"seq":13,"text":"正在分析..."}

event: done
data: {"content":"完整正文","length":1280}
```

错误事件使用：

```json
{
  "code": "LLM_TIMEOUT",
  "message": "生成超时，请重试",
  "retryable": true
}
```

迁移期消费者同时兼容 JSON 载荷与旧纯文本载荷。

### 5.2 SSEDecoder

解析器必须：

- 使用增量 `TextDecoder`；
- 按空行结束一个事件；
- 合并同一事件的多行 `data:`；
- 支持 `\n`、`\r\n`、多事件单分片及单事件多分片；
- 正确处理被拆开的 UTF-8 中文字符；
- 在流结束时刷新残余缓冲；
- 保留正文中真实存在的 `data:`；
- 安全忽略并记录未知事件。

### 5.3 StreamAccumulator

统一状态：

```text
idle -> connecting -> thinking -> streaming -> completed
                                      |-> interrupted
                                      |-> failed
```

token 写入内存缓冲，通过 `requestAnimationFrame` 刷新 React。`done` 到达时强制刷新最后一个 token。

服务端 `done.content` 是权威正文。若前端累计正文与它不一致，前端使用服务端正文覆盖，并记录 `STREAM_CONTENT_MISMATCH`。

### 5.4 Markdown 渲染

流式与完成态始终把累计全文交给同一个 `ReactMarkdown` 组件。`streaming` 只控制光标和状态标识，不改变解析方式。

删除“完整行使用 ReactMarkdown、当前行使用普通段落”的双树策略。流式光标放在 Markdown 容器之外。

对于未闭合的代码围栏，可仅在渲染副本中虚拟追加闭合围栏；真实正文不改变。表格、粗体、链接和公式在语法完整前按 Markdown 的自然渐进结果展示，不猜测补全。

### 5.5 完成态提升

对话收到 `done` 后，直接把流式消息提升为本地正式助手消息并更新 TanStack Query 缓存，再后台获取数据库消息校准。禁止先清空流式气泡、等待 refetch 后再显示。

简历评审仅切换状态，不切换 Markdown 解析策略。

### 5.6 中止与失败

用户主动停止时保留部分正文，标记“已停止生成”。网络中断时保留部分正文，标记“内容可能不完整”。收到部分正文后不自动重试，避免生成两份不同答案；尚未收到正文时允许一次瞬时网络重试。

## 6. 混合意图路由

### 6.1 RoutingDecision

```python
class RoutingDecision:
    domain: Literal["interview", "general"]
    topic_intent: Literal[
        "self_intro", "scenario", "technical", "career", "general"
    ]
    dialogue_act: Literal[
        "new_question", "continue", "clarify", "rewrite",
        "ask_interviewer_followup"
    ]
    source: Literal[
        "explicit_command", "rule", "fast_llm", "inherited", "fallback"
    ]
    confidence: float
    prompt_scope: str | None
    model_tier: Literal["fast", "pro"]
```

### 6.2 决策顺序

1. 显式 Slash Command；
2. 明确的对话行为规则；
3. 高置信度主题规则；
4. 低置信度时调用 Fast LLM；
5. 失败时继承上一主题或降级到 `general`。

显式命令具有最高优先级：

| 命令 | Topic | Dialogue Act |
|---|---|---|
| `/intro` | `self_intro` | `new_question` |
| `/scenario` | `scenario` | `new_question` |
| `/technical` | `technical` | `new_question` |
| `/followup` | 继承上一主题 | `ask_interviewer_followup` |

### 6.3 对话行为

- “继续追问”“再问我一个”识别为 `ask_interviewer_followup`。
- “更口语一点”“缩短刚才回答”识别为 `rewrite`。
- “为什么刚才这样做”“这个方案有什么缺点”识别为 `continue` 或 `clarify`。
- “为什么”“如何”“是什么”“我是”等弱词不能单独决定 Topic。

`/followup` 不再是 Topic，而是 Dialogue Act。

### 6.4 Topic 继承

`continue`、`clarify`、`rewrite`、`ask_interviewer_followup` 可以继承上一有效 Topic。显式新主题、Slash Command、“换个话题”等表达阻止继承。

### 6.5 Fast LLM 分类

只在规则信号冲突或依赖上下文时调用 Fast 模型。输入限制为当前文本、会话模式、上一 RoutingDecision、最近用户消息和最近助手回答的有限摘要，不加载完整简历、JD和附件。

分类使用 `temperature=0`、短超时、Pydantic Schema 校验和非流式 JSON 输出。超时或 JSON 无效时不阻塞生成。

### 6.6 普通与面试模式

两种模式使用同一个路由器：

- 面试模式默认 `domain=interview`，使用面试知识库和 Pro 模型；
- 普通模式先判断 Domain，面试相关请求加载知识库，通用请求使用 Fast 模型。

### 6.7 路由持久化与纠错

用户消息保存：

- `topic_intent`
- `dialogue_act`
- `routing_source`
- `routing_confidence`

SSE `meta` 返回有效路由。前端显示“技术题 · 延续追问”等自然语言标签，并提供“分类不对”入口。用户纠正后保留原回答，以指定路由重新生成，并将纠正记录为本地评测样本。

## 7. 统一上下文

### 7.1 构建顺序

```text
获取会话锁
-> 读取发送前的历史快照
-> 生成 RoutingDecision
-> 保存当前用户消息及路由元数据
-> 构建 ConversationContext
-> 调用生成模型
-> 保存助手消息
```

最终 LLM 消息顺序：

```text
System Prompt
-> 知识库上下文
-> 较早历史摘要
-> 最近原生历史
-> 当前用户消息一次
```

### 7.2 轮次选择

历史按业务轮次而非消息条数选取：

```python
class ConversationTurn:
    user_message: Message
    assistant_messages: list[Message]
    status: Literal["complete", "interrupted", "failed"]
```

- `new_question`：保留最近 2 至 4 轮；
- `continue` / `clarify`：固定原问题与目标回答，再补充近期轮次；
- `rewrite`：只固定被改写回答、原问题和当前要求；
- `ask_interviewer_followup`：固定最近一条同 Topic 的完整回答。

没有可追问回答时直接提示用户先完成一个问题，不调用模型。

### 7.3 生成状态

助手消息增加：

```text
generation_status = streaming | complete | interrupted | failed
```

中断或部分失败内容可以保存，但必须带状态。无正文的失败记录不作为正常助手回答进入 Prompt。

### 7.4 知识选择

不引入向量检索，使用确定性优先级：

- 始终保留当前身份、JD 核心要求及当前 Topic 相关技能；
- 自我介绍侧重代表项目、实习和岗位匹配；
- 技术题侧重技术栈、项目方案和结果；
- 场景题侧重挑战、协作、冲突和结果；
- 职业问题侧重求职方向、能力匹配和业务方向；
- 附件根据启用状态、Scope、Topic、关键词重合和用户明确提及进行筛选。

### 7.5 Token 预算

按模型上下文窗口预留：

- 15% 系统指令和安全余量；
- 25% 模型输出；
- 60% 知识、记忆、历史和当前问题。

输入保留优先级：

```text
P0 当前问题、System Prompt
P1 被固定目标轮次、JD 核心要求
P2 Topic 相关结构化简历、最近历史
P3 较早历史摘要
P4 附件原文
P5 低相关项目和技能
```

超限时从 P5 向 P3 裁剪，不能裁剪 P0 和固定目标轮次。

### 7.6 长期摘要

只在历史即将超出预算时生成结构化摘要，不每轮总结。摘要包含讨论主题、用户偏好、带来源消息 ID 的用户确认事实和尚未解决的问题。AI历史回答不能自动升级为用户事实。

### 7.7 Context Manifest

每次请求记录不含原文的上下文清单：路由、历史轮次 ID、固定轮次、Profile/JD/文档 ID、估算 Token、裁剪来源及摘要使用情况。禁止记录 API Key、完整资料、完整 Prompt 和完整回答。

## 8. 简历评审可信度

### 8.1 ReviewEvidenceBundle

评审前构建带证据 ID 的只读资料包，包含当前 Profile、经历、项目、技能、JD和启用附件。

### 8.2 内容分类

评审输出必须区分：

1. 已确认事实：可追溯到证据；
2. 缺失信息：使用 `[待补充]`；
3. 优化建议：使用建议语气，不能冒充已有成果。

### 8.3 禁止事项

- 不生成真实样式的虚构电话、邮箱、GitHub、学校、公司或时间；
- 没有证据时不生成性能提升、准确率、用户量、测试集规模等指标；
- 不把“类似”“建议学习”包装成已实现的 Function Calling 或其他技术经历。

### 8.4 输出与后置校验

评审固定包含摘要、维度评分、确认优势、缺失信息、岗位差距、修改建议、示例改写和待补充问题。

生成后规则检查联系方式、无依据数字、知识库不存在的技术声明及建议/事实混淆。轻微问题标记“需要确认”；严重问题不作为可信评审交付，并允许基于同一证据包重试。

## 9. 错误与恢复

内部标准错误包括：

- `SSE_PROTOCOL_ERROR`
- `STREAM_CONTENT_MISMATCH`
- `LLM_TIMEOUT`
- `LLM_AUTH_ERROR`
- `CLASSIFIER_TIMEOUT`
- `INVALID_CLASSIFIER_OUTPUT`
- `NO_FOLLOWUP_TARGET`
- `CONTEXT_BUDGET_EXCEEDED`
- `REVIEW_UNGROUNDED_CLAIM`
- `GENERATION_INTERRUPTED`

分类错误自动降级，不阻塞回答。正文生成失败保留已生成内容。重试简历评审时固定原 Profile、JD和附件 ID，防止知识切换造成混合结果。

## 10. 本地可观测性

记录请求 ID、Feature、路由、分类来源与置信度、模型、估算输入 Token、输出字符数、首字延迟、总耗时、流式一致性和最终状态。

日志仅保存在本地，设置数量或时间上限，禁止记录敏感原文和鉴权信息。

## 11. 数据迁移

新增字段均允许为空，旧消息不强制回填：

- `topic_intent`
- `dialogue_act`
- `routing_source`
- `routing_confidence`
- `generation_status`
- 生成时使用的 `profile_id`、`jd_id` 和文档 ID 清单

读取旧消息时：无路由元数据则视为未知 Topic；完整助手正文默认 `generation_status=complete`。

阶段二保留旧路由实现作为短期回滚开关，稳定后删除。

## 12. 测试

### 12.1 后端单元测试

- Topic、Dialogue Act、置信度及继承；
- Fast LLM 超时和无效 JSON 降级；
- 上下文去重、轮次选择、状态与预算；
- Review Evidence、数字、联系方式和技术声明检查。

### 12.2 前端单元测试

- SSE 任意字节分片、多行数据、CRLF、UTF-8和残余缓冲；
- Markdown 标题、列表、引用、代码、表格和公式渐进渲染；
- 最终正文校准、状态机、中止和无空白帧；
- 路由纠正和重新生成。

### 12.3 契约与 E2E 测试

所有流式端点共享同一 SSE 契约。E2E 使用 Fake LLM 流验证对话 Markdown、评审表格、自然语言追问、用户纠错、中断保留和会话隔离，不依赖真实模型 API。

### 12.4 意图评测集

覆盖所有 Topic、Dialogue Act、冲突表达、短口语、弱关键词干扰、上下文继承和普通/面试边界。显式命令必须 100% 正确；“请求面试官追问”优先保证召回；高置信度规则优先保证精确率。

## 13. 验收标准

### 流式

- 不引入额外 `data:`；
- 前端累计内容等于 `done.content`；
- 对话和评审共用解析器与刷新策略；
- 完成时消息不消失；
- 中止后保留部分内容。

### 路由

- 显式命令准确率 100%；
- “继续追问我”进入面试官追问；
- “为什么刚才这样做”继承上一 Topic；
- “为什么离职”不判为技术题；
- 用户可以纠正并重新生成。

### 上下文

- 当前问题和历史各出现一次；
- 追问固定正确目标回答；
- 不跨 Session、Profile和JD；
- 中断状态明确；
- 超限先裁剪低优先级资料。

### 简历评审

- 不虚构联系方式、项目指标或技术经历；
- 缺失信息使用占位符；
- 建议与事实明确分离；
- 能定位知识来源。

## 14. 实施阶段

### 阶段一：流式链路

完成 SSE 协议、解析器、StreamAccumulator、单一 MarkdownRenderer、完成态提升及相关测试。

### 阶段二：混合路由与上下文

完成 RoutingDecision、双维分类、Fast LLM 分类、ConversationContextBuilder、消息元数据和分类测试集。

### 阶段三：可信评审与纠错

完成 ReviewEvidenceBundle、事实约束、后置校验、分类纠错、本地诊断和 E2E 回归。

三个阶段独立验收和回滚。实施必须遵循项目 Bug 修复流程：先增加失败测试并复现，再逐项修改，最后进行真实页面与自动化验证。
