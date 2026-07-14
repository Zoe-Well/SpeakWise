结合你的 **spec-kit 开发规范**、**Vibe Coding 快节奏** 特性，以及 **Claude（推理/解析） + DeepSeek-V4-Pro（生成/执行）** 的双模型策略，我为你设计了一套 **“分层解耦、AI原生、极速迭代”** 的技术栈架构。

这套架构的核心思路是：**后端负责“稳”（数据与逻辑），AI层负责“智”（路由与生成），前端负责“快”（Vibe友好）**。

---

### 1. 核心架构全景图（分层设计）

| 层级 | 技术选型 | 职责 | 适配 spec-kit 的原因 |
| :--- | :--- | :--- | :--- |
| **前端层** | **React 18 + Vite + Tailwind CSS** | 简历表单、Chat UI、流式打字机效果 | Vite 热更新极快，极适合 Vibe Coding 的“即时反馈”循环。Tailwind 让 AI（Claude）生成 UI 代码时命中率极高。 |
| **后端核心** | **Python 3.11 + FastAPI** | RESTful API、SSE（流式推送）、数据校验 | Pydantic v2 完美契合你的数据结构（简历/JD Schema），且异步性能支撑 LLM 的高并发等待。 |
| **AI 编排层** | **LangChain (Core) + 自定义适配器** | Prompt 模板管理、模型路由（Router）、输出解析 | LangChain 的 `RunnableSequence` 能完美实现你的 **“硬规则+软适应”** 控制逻辑。 |
| **数据存储** | **PostgreSQL (含 pgvector 插件) + Redis** | 结构化数据存储 + 向量记忆缓存 + 对话状态 | PostgreSQL 的 JSONB 字段可灵活存储“实习/科研”等非固定结构数据；Redis 缓存 JD 解析结果，避免重复消耗 Claude Token。 |
| **基础设施** | **Docker Compose** | 一键启动开发环境（App + DB + Redis） | 确保 spec-kit 的 `plan->task` 环境一致性，杜绝“在我电脑上能跑”的问题。 |

---

### 2. 针对你核心诉求的“技术专项设计”

#### A. 双模型路由层（解决“Claude + DeepSeek-V4-Pro”分工）
不要用单一模型硬扛，采用 **“思考-执行”分离**：

- **Claude（思考/规划角色）**：负责 **JD 解析**（提取技能树、业务场景）和 **复杂逻辑判断**（例如：判断用户经历与 JD 的匹配度，决定走“强匹配”还是“弱匹配/学习补偿”分支）。*（利用 Claude 强大的长上下文和推理能力）*
- **DeepSeek-V4-Pro（执行/写作角色）**：负责 **最终话术生成**。将 Claude 规划好的“大纲骨架”+ 你的简历事实，灌给 DeepSeek 进行“润色填充”。*（利用 DeepSeek 的高性价比和中文自然度）*
- **技术实现**：使用 **策略模式 (Strategy Pattern)** 封装两个 LLM 客户端，通过配置文件即可切换，无需改业务代码。

#### B. 提示词工程引擎（满足你的“Prompt 控制 + LLM 自适应”）
不要将 Prompt 写在代码里，建立 **Prompt 注册中心 (Registry)**：

- 使用 **YAML 文件** 管理 System Prompt 模板（对应你 Spec 中的第 5 节）。
- 引入 **`jinja2` 模板引擎**：将 `{resume_json}`、`{jd_analysis}`、`{user_control_switch}` 动态注入。
- **LangChain 的 `OutputFixingParser`**：强制 DeepSeek 输出 JSON 或 Markdown 格式，确保前端能稳定解析“概述/技能/步骤”等字段，方便你进行 UI 高亮渲染。

#### C. 流式交互（解决“面试流畅感”）
面试场景极其看重“首字延迟”和“边想边说”的体验：

- **后端**：FastAPI 使用 **`StreamingResponse`** 配合异步生成器，将 DeepSeek 的流式输出直接推送到前端。
- **前端**：React 使用 **`@microsoft/fetch-event-source`** 接收 SSE，配合 `react-markdown` 实时渲染打字机效果。

#### D. 状态与记忆管理（应对“场景题连续追问”）
场景题往往有追问（例如：“如果这个方案被否定了呢？”）：

- 使用 **Redis** 存储当前面试会话的 `session_id` 对应的上下文窗口。
- **技术策略**：不无限塞历史消息（防止 Token 爆炸），而是利用 **LangChain 的 `ConversationSummaryMemory`**，每轮对话后由 Claude 生成一句话摘要存入 Redis，仅将“摘要 + 最新问题”发给 DeepSeek 生成回答。

---

### 3. 对接 spec-kit 的目录结构建议（Plan 阶段可直接用）

为了让 spec-kit 的 `plan` 和 `task` 拆解得更清晰，建议后端采用 **领域驱动设计（DDD）轻量级分层**，与你的 Spec 模块一一对应：

```text
backend/
├── app/
│   ├── api/                # 接口层（对应 FastAPI 路由）
│   │   ├── endpoints/
│   │   │   ├── profile.py  # 存储简历数据 (Spec 模块 A)
│   │   │   ├── jd.py       # 接收 JD 并触发解析 (Spec 模块 B)
│   │   │   └── interview.py# 生成自我介绍/场景题 (Spec 模块 C/D)
│   ├── core/               # 核心业务逻辑（最关键）
│   │   ├── llm_router.py   # 路由策略：Claude->解析, DeepSeek->生成
│   │   ├── prompt_engine.py# 加载 YAML 模板，注入变量 (Spec 第 5 节)
│   │   └── context_builder.py# 组装“硬规则+软适应”的上下文
│   ├── models/             # Pydantic Schemas (严格对应你的数据实体)
│   │   ├── resume.py       # 实习/科研/技术栈
│   │   └── jd.py           # 解析后的技能与职责
│   └── services/           # 外部服务适配器
│       ├── claude_client.py
│       └── deepseek_client.py
├── prompts/                # 提示词工程仓库 (纯文本/YAML)
│   ├── self_intro_v1.yaml
│   └── scenario_v1.yaml
└── docker-compose.yml
```

---

### 4. 针对“Vibe Coding”的特殊工具链建议

既然你在进行 Vibe Coding，建议加入以下工具让 AI（Claude/Cursor）写代码更精准：

1.  **类型强制**：后端严格使用 **`mypy`**  + 前端严格使用 **TypeScript**。强类型能让 AI 在生成代码时自动补全字段，极大减少“幻觉字段”（比如把 `achievements` 写成 `achieve`）。
2.  **API 契约先行**：使用 **`prisma`**（若换 Node）或 **`openapi-generator`**（Python）。建议先由 Claude 生成 `openapi.json`（接口文档），再让 AI 基于文档生成前后端代码，保证数据对接零误差。
3.  **Embedding 轻量检索**：针对你 Spec 里的“可选 RAG”，不要一上来装 Chroma。直接用 **PostgreSQL + pgvector**，当用户提问场景题时，用 DeepSeek 的 Embedding 模型将问题向量化，在库中检索最相关的“项目经历”拼接到 Prompt 中。

---

### 5. 总结：为什么这套架构最适合你？

| 你的痛点 | 这套架构的解法 |
| :--- | :--- |
| **双模型切换（Claude/DeepSeek）** | 适配器模式，换模型只需改一行环境变量，无需动业务代码。 |
| **Prompt 需要频繁调优（硬/软规则）** | Prompt 外置于 YAML 文件，修改无需重启服务，甚至可以在前端埋个“调试面板”直接热更新。 |
| **流利度与逻辑性** | 利用 Claude 打草稿（逻辑骨架）+ DeepSeek 扩充（血肉文字），兼顾深度与速度。 |
| **spec-kit 的规范落地** | 目录结构严格对应 `Spec -> Plan -> Task`，每个 Task（如“生成自我介绍”）都对应 `core/` 下的一个独立函数，易于测试和回滚。 |
