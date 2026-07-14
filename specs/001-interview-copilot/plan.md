# 实现计划 (Implementation Plan)：智能面试助手（Interview Copilot）

**Branch**: `001-interview-copilot` | **Date**: 2026-07-10 | **Spec**: [spec.md](./spec.md)

**Input**: 功能规格来自 [`specs/001-interview-copilot/spec.md`](./spec.md)

## 摘要 (Summary)

面向求职者的智能面试助手，核心交付两大能力：**岗位定制化自我介绍生成**（三段式：概述 → 技能+证据 → 业务匹配）与**场景题/行为题 STAR 结构化回答**。系统持久化用户的结构化个人经历（简历/实习/项目/技术栈），结合岗位上下文（JD/公司介绍），采用"硬规则控制 + 软自适应"双轨机制生成流利、可信、防穿帮的话术。

**技术路线**：Electron 桌面壳承载 React（Shadcn/ui + Tailwind CSS）前端，通过本地 Python/FastAPI 服务提供能力；结构化数据落在本地 SQLite；全流程使用**单一 LLM（DeepSeek-V4-Pro）**完成 JD 解析与话术生成，经 LLM 客户端抽象层封装；流式（SSE）输出实现打字机效果。RAG 语义检索（Pgvector）作为上下文超长时的**可选后续增强**，MVP 不启用。

## 技术上下文 (Technical Context)

**Language/Version**: 后端 **Python 3.12**（`>=3.12,<3.13`）；前端 TypeScript 5.5（React 18.3 + Vite 5）；桌面壳 Electron 32（Node.js 20 LTS）

**Primary Dependencies**（版本已对齐 Python 3.12）：
- 后端：FastAPI 0.115.x、Uvicorn[standard] 0.32.x、Pydantic 2.9.x、SQLModel 0.0.22（SQLAlchemy 2.0.x）、httpx 0.27.x、sse-starlette 2.1.x、python-multipart（文件上传）
- 文档解析：pypdf 5.x（PDF 文本层提取）、python-docx 1.1.x（DOCX）；TXT 原生读取；旧版 `.doc` 经可选 LibreOffice headless 转换（后续）
- 前端：React 18.3、Vite 5.x、Tailwind CSS 3.4、shadcn/ui（Radix UI + lucide-react）、TanStack Query 5.x
- 桌面：Electron 32.x、electron-builder 25.x；**悬浮实时辅助窗**（独立的 frameless / transparent / alwaysOnTop 置顶窗口，`setOpacity` 调透明度、可拖拽）
- LLM：DeepSeek-V4-Pro（单一模型，经 openai 1.x OpenAI 兼容 SDK 调用，封装于内部 `llm` 抽象层）
- 测试：pytest 8.3.x、pytest-asyncio 0.24.x（后端）；Vitest 2.x + React Testing Library（前端）
- 可选（后续）：PostgreSQL 16 + pgvector 0.7+、嵌入模型（用于 RAG 检索）；扫描件 OCR

**Storage**: 本地 SQLite（结构化真源，文件位于 `data/copilot.db`）；JD 原文缓存于 `data/jd_cache/`；Pgvector 向量库为可选后续能力，MVP 不引入。

**Testing**: 后端 pytest（contract / integration / unit）；前端 Vitest + React Testing Library（关键交互）

**Target Platform**: Windows / macOS / Linux 桌面（Electron 打包），单用户本地运行

**Project Type**: 桌面应用（Electron 前端 + 本地 FastAPI 后端），前后端分离多组件结构

**Performance Goals**（源自 Success Criteria）：
- 生成首字延迟 < 2s；完整话术生成 < 15s（SC-004）
- 自我介绍输出约 300–400 字 / 1–2 分钟朗读，达标率 ≥ 90%（SC-005）

**Constraints**:
- 单用户、私有化、本地存储；个人数据仅本人可见
- 生成默认中文；不含语音识别/实时转录
- 相同输入的核心事实一致性（生成温度建议 0.3–0.5，兼顾精准与自然）
- 弱匹配防穿帮：不得编造与用户无关的工作经历

**Scale/Scope**: 单用户；数十条经历量级；8 个用户故事（US1 /intro 自我介绍 / US2 /scenario 场景题 / US2b /followup 模拟追问 / US3 知识库 / US4 文档导入 / US5 悬浮辅助 / US6 多轮对话多会话 / US7 语音扩展 / US8 提示词管理）；40 条功能需求。交互主线为对话流（类 ChatGPT），斜杠命令触发生成，独立页面仅保留"个人知识库""岗位上下文""提示词管理"三个配置页。

## 宪法检查 (Constitution Check)

*GATE：Phase 0 研究前必须通过；Phase 1 设计后复检。*

依据 `.specify/memory/constitution.md`（**v1.0.0**）的五项核心原则逐条评估：

| 原则 | 本计划的符合性 |
|------|--------------|
| I. 事实锚定，绝不穿帮 | ✅ `GeneratedResponse.source_experience_ids` 记录来源经历；Prompt 内置"弱匹配角度切换、不得编造无关经历"约束（research §8） |
| II. 双轨控制 | ✅ 分层 Prompt（USER_CONTROL 硬规则 + 软自适应）+ 三段式/编号步骤程序校验（research §5/§7） |
| III. 数据私有化，单用户本地优先 | ✅ 本地 SQLite 单用户存储；除必需的 LLM 调用外不外传；支持查看/编辑/删除 |
| IV. 可度量、可验证、可复现 | ✅ 需求映射 SC-xxx；温度 0.3–0.5；LLM 打桩的分层测试（research §10） |
| V. 规格驱动开发 | ✅ 遵循 spec→plan→tasks；spec 保持实现无关，技术决策落在 plan/research |

**质量与安全约束**：性能目标（首字 <2s、完整 <15s）、单一模型经 `llm/` 抽象层、JD 失败降级、中文默认——均已在技术上下文与契约中体现。

- 复杂度提示：本计划引入 Electron + React + FastAPI + SQLite（+可选 Pgvector）多组件，属于用户显式选择的技术栈；已通过"RAG 延后、单一模型、单文件 SQLite"等方式控制初期复杂度，详见 [research.md](./research.md) 与下方复杂度追踪表。

**Post-Design 复检结论**：设计工件（data-model / contracts / quickstart）未引入超出上述技术栈的额外复杂度；对五项原则无违规项。门禁通过。

## 项目结构 (Project Structure)

### 本功能文档 (Documentation)

```text
specs/001-interview-copilot/
├── plan.md              # 本文件（/speckit-plan 输出）
├── research.md          # Phase 0：技术决策与取舍
├── data-model.md        # Phase 1：实体与关系
├── quickstart.md        # Phase 1：端到端验证指南
├── contracts/           # Phase 1：接口契约
│   └── api-contracts.md
├── checklists/
│   └── requirements.md  # 规格质量检查清单（/speckit-specify 输出）
└── tasks.md             # Phase 2 输出（/speckit-tasks，本命令不创建）
```

### 源码结构 (Source Code, repository root)

```text
speakwise/
├── electron/                 # Electron 主进程：窗口管理、启动并托管本地 FastAPI 后端
│   ├── main.js
│   ├── preload.js
│   └── overlay.js            # 悬浮实时辅助窗（frameless/transparent/alwaysOnTop，透明度/拖拽/置顶）
├── frontend/                 # React + Vite + TS + Tailwind + shadcn/ui
│   ├── src/
│   │   ├── components/        # shadcn/ui 基础组件 + 业务组件
│   │   │   ├── ChatView.tsx          # 对话流主视图（唯一主界面）
│   │   │   ├── MessageBubble.tsx     # 对话消息气泡（用户/助手/自我介绍/STAR 卡片）
│   │   │   ├── ChatInput.tsx         # 输入栏：斜杠命令 + 自动补全 + 语音按钮 + 发送
│   │   │   ├── SlashCommandMenu.tsx  # / 触发的命令补全下拉菜单
│   │   │   ├── SessionHeader.tsx     # 会话顶部栏（会话名/JD/模板选择器/呈现控件）
│   │   │   ├── DocumentImport.tsx
│   │   │   ├── ConfirmMergeDialog.tsx
│   │   │   ├── OverlayPanel.tsx
│   │   │   └── DisplaySettings.tsx
│   │   ├── pages/            # 知识库管理页、岗位上下文页（独立的"配置"页）
│   │   ├── lib/             # API 客户端、SSE 流式处理、斜杠命令解析器、类型定义
│   │   └── App.tsx
│   └── tests/
├── backend/                  # Python FastAPI 本地服务
│   ├── src/
│   │   ├── models/           # Pydantic/SQLModel 数据模型（Profile/Experience/JD/Directive/Response/Document/DisplaySettings）
│   │   ├── services/         # profile_service, jd_analyzer, generation_service,
│   │   │   │                 #   conversation_service（斜杠命令路由 + 上下文组装）,
│   │   │   │                 #   document_parser（TXT/PDF/DOCX 提取 + 结构化建议）, retrieval(可选)
│   │   ├── prompts/          # 分层 Prompt 模板与版本管理（SYSTEM_ROLE / USER_CONTROL / DYNAMIC_CONTEXT）
│   │   ├── llm/             # LLM 客户端抽象（单模型：DeepSeek-V4-Pro）+ 流式封装
│   │   ├── api/             # FastAPI 路由（profile / experiences / skills / jd / generate / directives / documents / settings）
│   │   ├── db/             # SQLite 连接与迁移；pgvector 检索（可选/后续）
│   │   └── main.py          # FastAPI app 入口
│   └── tests/
│       ├── contract/         # 接口契约测试
│       ├── integration/      # 端到端生成流程测试
│       └── unit/            # Prompt 组装、长度/结构校验、文档解析等单测
├── data/                     # 本地 SQLite 数据库文件、JD 缓存、导入文档缓存
└── specs/
```

**Structure Decision**：采用**桌面应用（Electron）+ 本地后端（FastAPI）+ 前端（React/shadcn/ui）**的多组件结构。Electron 主进程在启动时拉起本地 FastAPI 子进程，前端通过 `http://127.0.0.1:<port>` 与后端通信、经 SSE 接收流式生成。数据默认落本地 SQLite。此结构对应用户选定的技术栈，并为后续引入 Pgvector RAG 预留 `backend/src/db` 与 `services/retrieval` 扩展位。

## 复杂度追踪 (Complexity Tracking)

> 仅在宪法检查存在需辩护的违规时填写。

当前宪法为模板占位符、无门禁，故无违规项需要辩护。已知复杂度来源（多组件技术栈）系用户显式选择，并通过以下手段控制：

| 复杂度来源 | 为何需要 | 控制方式 |
|-----------|---------|---------|
| Electron + React + FastAPI 多组件 | 用户指定的交付形态与技术栈 | 后端单体本地服务；前端复用 shadcn/ui 组件；Electron 仅做壳与进程托管 |
| Pgvector 向量库 | 上下文超长时的 RAG 检索 | MVP 不启用；128k 上下文直接注入；列为后续增强，预留扩展位 |
| 双数据存储（SQLite + 可选 Pgvector） | 结构化真源 vs 语义索引职责不同 | SQLite 为唯一真源；Pgvector 仅为派生索引，可随时重建 |

---

## Phase 0 / Phase 1 产物

- **Phase 0**：[research.md](./research.md) — 已解决全部技术决策，无遗留 NEEDS CLARIFICATION。
- **Phase 1**：[data-model.md](./data-model.md)、[contracts/api-contracts.md](./contracts/api-contracts.md)、[quickstart.md](./quickstart.md)。
- **Agent 上下文**：已更新根目录 `CLAUDE.md` 的 SPECKIT 标记指向本计划。

**下一步**：运行 `/speckit-tasks` 生成 `tasks.md`（本命令不创建）。
