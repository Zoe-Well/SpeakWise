# 任务清单 (Tasks)：智能面试助手（Interview Copilot）

**Input**: Design documents from [`specs/001-interview-copilot/`](./)

**Prerequisites**: [plan.md](./plan.md) (required), [spec.md](./spec.md) (required for user stories), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: 包含契约测试与集成测试任务（LLM 调用以 mock 打桩保证确定性）。

**Organization**: 任务按用户故事分组，支持独立实现与独立测试。Setup + Foundational 完成后用户故事可并行推进。

## Format: `- [ ] [ID] [P?] [Story] Description with file path`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup（项目初始化）

**Purpose**: 创建项目骨架，安装依赖，确保 Electron + React + FastAPI 三端可并行启动。

- [ ] T001 Create project directory structure per plan.md: `electron/`, `frontend/src/{components,pages,lib}`, `backend/src/{models,services,prompts,llm,api,db}`, `backend/tests/{contract,integration,unit}`, `data/`
- [ ] T002 [P] Initialize Python backend with `pyproject.toml` dependencies (FastAPI 0.115, Uvicorn[standard] 0.32, Pydantic 2.9, SQLModel 0.0.22, httpx 0.27, sse-starlette 2.1, openai 1.50+, pypdf 5.x, python-docx 1.1, python-multipart, pytest 8.3, pytest-asyncio 0.24) — run `uv sync`
- [ ] T003 [P] Initialize React + Vite + TypeScript frontend in `frontend/` with dependencies (React 18.3, Vite 5, Tailwind CSS 3.4, shadcn/ui, TanStack Query 5, Vitest 2)
- [ ] T004 [P] Initialize Electron shell in `electron/` with `main.js`, `preload.js`, `package.json` (Electron 32, electron-builder 25), configure to spawn local FastAPI backend on app ready
- [ ] T005 [P] Configure linting/formatting: Ruff for Python (`backend/`), ESLint + Prettier for TypeScript (`frontend/`)

---

## Phase 2: Foundational（基础架构 — 阻塞全部用户故事）

**Purpose**: 数据库、API 骨架、LLM 抽象层、前端壳——任何用户故事都依赖这些。

**⚠️ CRITICAL**: 本阶段完成前，不得开始用户故事实现。

- [ ] T006 Setup SQLite database connection and migration framework in `backend/src/db/connection.py` and `backend/src/db/migrations.py` (auto-create tables on first run)
- [ ] T007 [P] Create base SQLModel entities for UserProfile, Internship, Project, Skill in `backend/src/models/profile.py`
- [ ] T008 [P] Create FastAPI app entry point in `backend/src/main.py` with CORS (localhost), health check `GET /api/health`, lifespan for DB init
- [ ] T009 [P] Implement LLM abstraction layer in `backend/src/llm/client.py` with unified `chat()` and `stream()` interfaces, DeepSeek-V4-Pro as default provider via openai SDK, configurable via env `DEEPSEEK_API_KEY`
- [ ] T010 [P] Implement SSE streaming helper in `backend/src/llm/streaming.py` (sse-starlette wrapper, token-by-token yield)
- [ ] T011 [P] Create frontend app shell in `frontend/src/App.tsx` with sidebar navigation layout (React Router or state-based page switching), page placeholders for conversation/profile/jd/prompts
- [ ] T012 [P] Create API client library in `frontend/src/lib/api.ts` with base fetch wrapper, SSE event stream parser, and typed request/response helpers
- [ ] T013 [P] Implement Electron main process in `electron/main.js`: create BrowserWindow, spawn FastAPI subprocess on app ready, kill on app quit, load frontend dev server URL or built files
- [ ] T014 Create `data/` directory with `.gitkeep` for SQLite database file location

**Checkpoint**: 三端可用——后端 `uvicorn main:app` 返回 `{"status":"ok"}`；前端 `npm run dev` 展示侧边栏骨架；Electron 启动后加载前端。

---

## Phase 3: US3 — 个人知识库管理与复用 (Priority: P3, Foundational)

**Goal**: 用户能录入、查看、编辑、删除个人经历（简历/实习/项目/技能），数据跨会话持久化。

**Independent Test**: 录入一段实习、一个项目、若干技能后重启后端，数据仍存在且可编辑/删除。

### Tests for US3

- [ ] T015 [P] [US3] Contract test for profile CRUD in `backend/tests/contract/test_profile_api.py` (POST/GET/PUT/DELETE)
- [ ] T016 [P] [US3] Contract test for experiences & skills CRUD in `backend/tests/contract/test_experiences_api.py`

### Implementation for US3

- [ ] T017 [P] [US3] Implement Profile service (`backend/src/services/profile_service.py`) with CRUD for UserProfile, Internship, Project, Skill — validation rules per data-model §1–§4
- [ ] T018 [US3] Implement Profile API routes in `backend/src/api/profile.py`: `GET/POST/PUT /api/profile`, `GET/POST /api/experiences?type=internship|project`, `PUT/DELETE /api/experiences/{id}`, `GET/POST /api/skills`, `PUT/DELETE /api/skills/{id}`
- [ ] T019 [P] [US3] Create profile form page in `frontend/src/pages/ProfilePage.tsx`: basic info fields (name/phone/email)
- [ ] T020 [P] [US3] Create internship list + add/edit form components in `frontend/src/components/InternshipForm.tsx` with quantified achievements fields
- [ ] T021 [P] [US3] Create project list + add/edit form components in `frontend/src/components/ProjectForm.tsx` with role/tech_stack/challenge/solution/result fields
- [ ] T022 [P] [US3] Create skill chips + proficiency selector in `frontend/src/components/SkillManager.tsx`
- [ ] T023 [US3] Wire knowledge base page data flow: TanStack Query hooks ↔ API client ↔ backend CRUD, with optimistic update and toast feedback

**Checkpoint**: 知识库完全可用——录入、查看、编辑、删除经历与技能，重启后数据持久化。

---

## Phase 4: US6 — 多会话管理 (Priority: P2, Foundational for Conversation)

**Goal**: 用户可创建、切换、重命名、删除会话；每个会话有独立消息历史。会话是对话流的基础容器。

**Independent Test**: 创建 3 个会话并在它们之间切换，每个会话保留各自独立的消息历史。

### Tests for US6

- [ ] T024 [P] [US6] Contract test for sessions API in `backend/tests/contract/test_sessions_api.py` (create, list, switch, delete, cascade-delete messages)
- [ ] T025 [P] [US6] Contract test for messages API in `backend/tests/contract/test_messages_api.py` (list by session, pagination)

### Implementation for US6

- [ ] T026 [P] [US6] Create ConversationSession and Message SQLModel entities in `backend/src/models/session.py` per data-model §11–§12 (with `command` field on Message for slash command routing)
- [ ] T027 [US6] Implement session service in `backend/src/services/session_service.py`: create/list/rename/delete sessions, autoload messages, cascade-delete messages on session delete, auto-create "默认面试准备" on first launch
- [ ] T028 [US6] Implement session API routes in `backend/src/api/sessions.py`: `GET/POST /api/sessions`, `PUT/DELETE /api/sessions/{id}`, `GET /api/sessions/{id}/messages?before=<ts>&limit=50`
- [ ] T029 [P] [US6] Create session selector dropdown in sidebar (`frontend/src/components/SessionSelector.tsx`): list sessions, switch active, new/rename/delete with confirmation
- [ ] T030 [US6] Wire session state management in `frontend/src/lib/sessionStore.ts` (active session ID, cached message lists, TanStack Query invalidation on switch)

**Checkpoint**: 多会话可切换，消息历史独立，删除会话时消息级联删除。

---

## Phase 5: US1 — `/intro` 自我介绍生成 (Priority: P1) 🎯 MVP

**Goal**: 用户在对话中输入 `/intro [要求]`，系统生成三段式自我介绍并以流式打字机效果展示在对话气泡中。

**Independent Test**: 创建一个会话、确保有简历数据和 JD，输入 `/intro`，验证三段式结构与流式输出。

### Tests for US1

- [ ] T031 [P] [US1] Contract test for self-intro generation SSE endpoint in `backend/tests/contract/test_generate_intro.py` — verify `event:token` and `event:done` with section_check/three sections
- [ ] T032 [P] [US1] Integration test for `/intro` flow in `backend/tests/integration/test_intro_flow.py` — mock LLM, assert three-section structure, length 300–400 chars, source_experience_ids non-empty

### Implementation for US1

- [ ] T033 [P] [US1] Implement JobContext model and JD analysis service in `backend/src/services/jd_analyzer.py`: structured extraction (core_skills, duties, culture_values) via LLM with JSON schema output; status: pending→success/failed → fallback to generic mode
- [ ] T034 [P] [US1] Create JD context page in `frontend/src/pages/JDPage.tsx`: textarea for JD + company intro, "解析岗位" button, parsed result display (skill/duty/culture chips), fail simulation switch, JD document import button, attach materials affordance
- [ ] T035 [US1] Create layered prompt templates for self-intro in `backend/src/prompts/self_intro.py`: SYSTEM_ROLE, USER_CONTROL (3-section structure), DYNAMIC_CONTEXT (resume_json + jd_analysis); support optional requirement injection from `/intro [要求]`
- [ ] T036 [US1] Implement conversation service in `backend/src/services/conversation_service.py`: parse incoming message `command` field, route `/intro` → self-intro generation, assemble prompt with profile + JD context + session context window (recent N messages + summary of earlier), call LLM via abstraction layer, stream SSE
- [ ] T037 [US1] Implement generation API route in `backend/src/api/generate.py`: `POST /api/generate` accepting `{session_id, content, command, jd_context_id?, directive_id?}`, return SSE stream with `event:meta`/`event:token`/`event:done`
- [ ] T038 [US1] Create conversation main page in `frontend/src/pages/ConversationPage.tsx`: top toolbar (JD toggle, match-level seg, template selector, display mode, rate, auto-scroll), message list area, input bar with slash command support
- [ ] T039 [P] [US1] Create ChatInput component in `frontend/src/components/ChatInput.tsx`: text input, send button, `/` triggers slash command autocomplete dropdown (`/intro`, `/scenario`, `/followup`), Tab/click to autofill
- [ ] T040 [P] [US1] Create MessageBubble component in `frontend/src/components/MessageBubble.tsx`: user bubble (right-aligned, primary bg) + assistant bubble (left-aligned, card with copy button); support three-section label tags for self-intro output
- [ ] T041 [US1] Implement SSE stream consumer in `frontend/src/lib/streamConsumer.ts`: connect to `/api/generate` SSE, parse events, accumulate tokens, update message bubble reactively (typing effect), finalize on `done` with metrics (TTFB, word count, section check)
- [ ] T042 [US1] Wire full `/intro` flow: ChatInput send → API client POST → streamConsumer → MessageBubble live update → auto-scroll to bottom → enable copy action on done

**Checkpoint**: MVP 就绪——输入 `/intro` 即可获得三段式自我介绍，流式打字机输出，对话气泡展示。✅ 可独立演示/交付。

---

## Phase 6: US2 — `/scenario` 场景题回答生成 (Priority: P2)

**Goal**: 用户输入 `/scenario <问题>`，系统生成 STAR 结构化回答，行动部分含编号步骤。

**Independent Test**: 在已有经历的会话中输入 `/scenario 如果项目上线后崩溃了怎么办？`，验证输出含编号步骤（≥3）且可追溯到真实经历。

### Tests for US2

- [ ] T043 [P] [US2] Contract test for scenario generation in `backend/tests/contract/test_generate_scenario.py` — verify `done` event has `star_check` and `numbered_steps_count >= 3`
- [ ] T044 [P] [US2] Integration test in `backend/tests/integration/test_scenario_flow.py` — mock LLM, assert STAR structure, step labels ([止损],[排查],[修复],[复盘]), source_experience_ids anchored

### Implementation for US2

- [ ] T045 [P] [US2] Create scenario prompt templates in `backend/src/prompts/scenario.py`: STAR-L framework (Situation/Task → Action with numbered steps → Result), tone adaptation rules, experience anchoring constraints
- [ ] T046 [US2] Add `/scenario` command routing in `backend/src/services/conversation_service.py`: parse question text from command arg, inject scenario prompt, emit SSE; ensure shared-profile context from same session's previous turns
- [ ] T047 [US2] Add STAR message card styling in `frontend/src/components/MessageBubble.tsx`: numbered steps `<ol>` rendering, source experience banner ("🔗 来源经历：..."), tone badge (沉稳/进取)
- [ ] T048 [US2] Wire `/scenario` flow end-to-end: ChatInput → command parse → SSE → bubble with steps → copy action

**Checkpoint**: 自我介绍 + 场景题均在对话中可用。`/intro` 和 `/scenario` 可在同一会话中连续使用，共享上下文。

---

## Phase 7: US4 — 文档导入与素材附加 (Priority: P2)

**Goal**: 用户可导入 TXT/DOCX/PDF 文档，解析后形成知识库更新建议（需确认），或直接附加为素材。

**Independent Test**: 导入一份 PDF 简历 → 展示拟新增项 → 仅勾选项写入知识库 → 无自动覆盖。

### Tests for US4

- [ ] T049 [P] [US4] Contract test for document upload in `backend/tests/contract/test_documents_api.py` — POST multipart, verify parse_status, proposal structure
- [ ] T050 [P] [US4] Contract test for profile merge in `backend/tests/contract/test_profile_merge.py` — verify only accepted_change_ids written, rejected items unchanged

### Implementation for US4

- [ ] T051 [P] [US4] Create SourceDocument and ProfileUpdateProposal SQLModel entities in `backend/src/models/document.py` per data-model §8–§9
- [ ] T052 [US4] Implement document parser service in `backend/src/services/document_parser.py`: TXT native read, PDF via pypdf, DOCX via python-docx; extract text, generate structured update proposals (add/update internship/project/skill/profile fields); detect conflict with existing data; handle unsupported/unreadable gracefully
- [ ] T053 [US4] Implement document and merge API routes in `backend/src/api/documents.py`: `POST /api/documents` (multipart, scope=profile|jd, usage=parse|attach), `GET/DELETE /api/documents/{id}`, `POST /api/profile/merge` (accept proposal with selected change IDs)
- [ ] T054 [P] [US4] Create DocumentImport component in `frontend/src/components/DocumentImport.tsx`: drag-drop/file-picker dropzone, scope/usage selector, loading state, error state for unreadable files
- [ ] T055 [P] [US4] Create ConfirmMergeDialog component in `frontend/src/components/ConfirmMergeDialog.tsx`: list proposed changes with checkboxes, conflict highlighting, "确认写入所选" button, "取消" button
- [ ] T056 [US4] Add attached-document chips display to profile page and JD page (reuse existing `attached` chip rendering)

**Checkpoint**: PDF/DOCX 简历导入 → 确认弹窗 → 仅勾选写入 → 知识库更新。

---

## Phase 8: US8 — 提示词模板可视化管理 (Priority: P2)

**Goal**: 用户可在左侧面板集中管理生成模板——查看、编辑、新建、切换，内置模板 copy-on-edit 保护。

**Independent Test**: 编辑内置自我介绍模板 → 自动生成副本 → 切换后生成遵循新模板结构。

### Tests for US8

- [ ] T057 [P] [US8] Contract test for prompt templates in `backend/tests/contract/test_templates_api.py` — CRUD, built-in protection (403 on delete, copy-on-edit returns new ID), import/export

### Implementation for US8

- [ ] T058 [P] [US8] Create PromptTemplate SQLModel entity in `backend/src/models/template.py` per data-model §13 (scope, structure_rules JSON, style_rules JSON, is_builtin)
- [ ] T059 [US8] Implement template service in `backend/src/services/template_service.py`: CRUD, copy-on-edit for built-in, export/import as JSON, conflict detection on save (conflicting rules → 422)
- [ ] T060 [US8] Implement template API routes in `backend/src/api/templates.py`: `GET/POST /api/prompt-templates`, `PUT/DELETE /api/prompt-templates/{id}`, `POST /api/prompt-templates/{id}/export`, `POST /api/prompt-templates/import`
- [ ] T061 [US8] Create PromptTemplatePage in `frontend/src/pages/PromptTemplatePage.tsx`: list cards grouped by scope, built-in badge, "复制并编辑"/"编辑"/"删除" actions per template
- [ ] T062 [US8] Wire template selector in conversation toolbar: dropdown in `SessionHeader.tsx` populated from template list, `setActiveTemplate()` updates session's active template, switching persists to DB

**Checkpoint**: 提示词模板可集中管理、编辑（内置受保护）、切换——并在生成时生效。

---

## Phase 9: US5 — 悬浮实时辅助窗 (Priority: P3)

**Goal**: 生成内容可选在置顶悬浮窗中展示，支持透明度调节、整体拖拽、自动滚动。

**Independent Test**: 切换到悬浮方式生成一段回答 → 悬浮窗置顶 → 拖动到屏幕任意位置 → 调节透明度/速率即时生效。

### Implementation for US5

- [ ] T063 [P] [US5] Create DisplaySettings SQLModel entity in `backend/src/models/settings.py` per data-model §10 (mode, opacity, position, stream_speed, auto_scroll, scroll_speed)
- [ ] T064 [US5] Implement display settings API routes in `backend/src/api/settings.py`: `GET/PUT /api/settings/display` (opacity clamped to ≥35%, defaults)
- [ ] T065 [US5] Create Electron overlay window in `electron/overlay.js`: frameless, transparent, alwaysOnTop BrowserWindow; `setOpacity()` with lower-bound clamp; whole-window drag via `-webkit-app-region: drag` + manual `mousedown/mousemove` → `win.setPosition` (exclude interactive controls from drag); close button
- [ ] T066 [P] [US5] Create OverlayPanel component in `frontend/src/components/OverlayPanel.tsx`: render message content in overlay via IPC or shared state; opacity slider, pause/resume auto-scroll button, word count display in footer
- [ ] T067 [US5] Wire display mode toggle: conversation toolbar "面板/悬浮" toggle → `setDisplayMode()` → when floating, route generated content to overlay window via Electron IPC; stream consumer sends tokens to overlay in real-time

**Checkpoint**: 悬浮窗置顶拖拽 + 透明度 + 自动滚动全部可用。

---

## Phase 10: US2b — `/followup` 模拟追问 (Priority: P3)

**Goal**: 用户输入 `/followup`，AI 基于当前会话上下文自动生成一个面试官追问。

**Independent Test**: 先 `/intro` 再 `/scenario`，然后 `/followup`——验证追问内容与上述上下文相关。

### Implementation for US2b

- [ ] T068 [US2b] Add `/followup` command routing in `backend/src/services/conversation_service.py`: assemble recent context from session messages, generate a plausible interviewer follow-up question (e.g., digging into a weak point or expanding a technical detail)
- [ ] T069 [US2b] Style `/followup` message bubble in `frontend/src/components/MessageBubble.tsx`: "🤔 模拟面试官追问" header, copiable question text

---

## Phase 11: US7 — 语音输入扩展占位 (Priority: P3)

**Goal**: 语音输入扩展点——麦克风按钮 + 扩展注册接口。不实现具体语音识别，预留插件接入。

**Independent Test**: 未配置扩展时麦克风禁用且提示；注册模拟适配器后按钮可用。

### Implementation for US7

- [ ] T070 [P] [US7] Create VoiceAdapter SQLModel entity in `backend/src/models/voice_adapter.py` per data-model §14 (name, adapter_type, enabled, settings JSON)
- [ ] T071 [US7] Implement voice adapter API routes in `backend/src/api/voice.py`: `GET/POST /api/voice-adapters`, `PUT/DELETE /api/voice-adapters/{id}`, `GET /api/voice-adapters/active` (404 if none enabled → UI disables mic)
- [ ] T072 [US7] Add microphone button to ChatInput in `frontend/src/components/ChatInput.tsx`: disabled state when no active adapter (greyed out with tooltip "请先配置语音识别扩展"), enabled state when adapter registered; onClick → calls active adapter's transcribe method (client-side), inserts result into input field (editable before send)

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: 跨故事的质量打磨。

- [ ] T073 [P] Implement context window management in `backend/src/services/conversation_service.py`: when session messages exceed ~100k token threshold, summarize early messages retaining "discussed experiences + key decisions", inject summary into prompt
- [ ] T074 [P] Add error handling and retry across all generation flows: LLM timeout → user-friendly error bubble with retry button; network error → toast + auto-retry once
- [ ] T075 [P] Implement auto-scroll refinement: smooth pixel-by-pixel scroll during streaming via requestAnimationFrame; pause on user scroll interaction, resume after 3s idle or on new token
- [ ] T076 Performance optimization: TanStack Query caching for profile/sessions/templates/messages; virtualized message list for long conversations (optional)
- [ ] T077 Run full quickstart.md validation (scenarios A–L), fix any gaps
- [ ] T078 [P] Update `CLAUDE.md` SPECKIT block with final artifact links

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Setup ──► Phase 2: Foundational ──► Phase 3: US3 (KB)
                                         └─► Phase 4: US6 (Sessions)
                                                   └─► Phase 5: US1 (/intro) 🎯 MVP
                                                         ├─► Phase 6: US2 (/scenario)
                                                         ├─► Phase 7: US4 (Documents)
                                                         ├─► Phase 8: US8 (Templates)
                                                         ├─► Phase 9: US5 (Overlay)
                                                         ├─► Phase 10: US2b (/followup)
                                                         └─► Phase 11: US7 (Voice)
                                                               └─► Phase 12: Polish
```

- **Phase 2 blocks all user stories** — must complete before any story work begins
- **US3 and US6 can run in parallel** after Foundational (different files, different services)
- **US1 needs US6** (conversation page + sessions), and benefits from US3 (real data, but can dev with mock)
- **US2–US8 can run in parallel after US1** (each adds independent capability to the conversation flow)
- **Phase 12 runs after all desired stories are complete**

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD where tests are included)
- Models → Services → API routes → Frontend components → Wire end-to-end
- [P] tasks within a story can run in parallel (different files)

### Parallel Opportunities

```bash
# Within Setup (Phase 1): T002, T003, T004, T005 all in parallel
# Within Foundational (Phase 2): T007, T009, T010, T011, T012, T013 all [P]
# After Foundational: US3 + US6 can start in parallel (different services, different UI pages)
# After US1 complete: US2, US4, US8, US5, US2b, US7 can ALL start in parallel
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Phase 1: Setup (T001–T005)
2. Phase 2: Foundational (T006–T014) — **CRITICAL, blocks everything**
3. Phase 3: US3 — Knowledge Base (data layer needed by US1)
4. Phase 4: US6 — Sessions (conversation container needed by US1)
5. Phase 5: US1 — `/intro` 自我介绍生成
6. **STOP and VALIDATE**: `/intro` produces three-section self-intro in chat bubble with streaming
7. Deploy/demo 🎯

### Incremental Delivery

```
Setup + Foundational ──► Foundation ready
  + US3 (KB)          ──► Data entry works
  + US6 (Sessions)    ──► Multi-session management works
  + US1 (/intro)      ──► 🎯 MVP — deploy/demo
  + US2 (/scenario)   ──► Full generation capabilities
  + US4 (Documents)   ──► Import your existing resume
  + US8 (Templates)   ──► Customize generation style
  + US5 (Overlay)     ──► Interview teleprompter mode
  + US2b (/followup)  ──► Practice pressure questions
  + US7 (Voice)       ──► Hands-free input
  + Polish            ──► Production quality
```

### Parallel Team Strategy

With multiple developers after Foundational:
- Developer A: US3 (KB) + US6 (Sessions) → then US1 (/intro)
- Developer B: US4 (Documents) + US8 (Templates)
- Developer C: US5 (Overlay) + US7 (Voice)
- Stories complete and integrate independently into shared conversation infrastructure

---

## Notes

- [P] tasks touch different files and have no dependencies — safe to parallelize
- [Story] labels (US1–US8) map each task to a spec user story for traceability
- File paths follow plan.md structure (`backend/src/`, `frontend/src/`, `electron/`)
- LLM calls in tests must be **mocked/stubbed** for deterministic results per constitution §IV
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Each user story delivers an independently testable increment of value
