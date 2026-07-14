# SpeakWise — 智能面试助手（Interview Copilot）

## 技术栈

- **前端**: React 18.3 + TypeScript + Tailwind CSS 3.4 + Vite 5
- **后端**: Python 3.12 / FastAPI + SQLModel + SQLite + SSE 流式
- **桌面**: Electron 43（根目录 main.js，入口在项目根不在 electron/ 目录）
- **LLM**: DeepSeek V4 Pro（主模型）+ deepseek-chat（快速模型）
- **端口**: 前端 5173，后端 8001（8000 被僵尸进程占用）

## 启动

```powershell
# 终端 1 — 前端
cd frontend && npm run dev

# 终端 2 — 后端（开发调试时）
uv run uvicorn backend.src.main:app --host 127.0.0.1 --port 8001 --reload

# 或 Electron（需要提词器时，会自动拉起后端）
$env:NODE_ENV="development"; npx electron .
```

## 项目结构

```
SpeakWise/
├── main.js              ← Electron 主进程入口（根目录，避免 node_modules/electron 冲突）
├── package.json         ← Electron 用（"main": "main.js"）
├── .env                 ← DEEPSEEK_API_KEY（gitignore 保护）
├── .env.example         ← 模板
├── CLAUDE.md
├── backend/src/
│   ├── main.py          ← FastAPI 入口
│   ├── api/             ← generate, sessions, profile, templates, jd, documents, settings, voice
│   ├── db/connection.py ← SQLite + 迁移
│   ├── llm/client.py    ← LLMClient（DeepSeek 兼容 OpenAI SDK）
│   ├── models/          ← session, profile, template, document, job_context, settings, voice_adapter
│   ├── prompts/         ← self_intro, scenario, technical
│   └── services/        ← conversation_service, session_service, profile_service, jd_analyzer
├── frontend/src/
│   ├── App.tsx
│   ├── pages/           ← ConversationPage, ProfilePage, JDPage, PromptTemplatePage
│   ├── components/      ← ChatInput, MessageBubble, MarkdownRenderer, Toast, SessionSelector, DocumentImport, ConfirmMergeDialog
│   ├── lib/             ← api.ts, streamConsumer.ts
│   └── types/           ← electron.d.ts
├── electron/            ← Electron 辅助文件（overlay.html, preload.js, overlay-preload.js）
└── data/                ← copilot.db, overlay-settings.json
```

## 核心架构决策

### SSE 流式协议
```
event: meta       → {command, session_id, session_mode, fast_mode}
event: thinking   → 系统推理步骤 + LLM 原生 reasoning_content（累积为一个字符串）
event: token      → 回答正文片段
event: done       → {content, length}
event: error      → "生成失败，请重试"（不泄露原始异常）
```

### 模型路由
- 面试模式：deepseek-v4-pro（带 reasoning_content）
- 普通模式：classify_message() 判断是否面试相关 → pro 或 deepseek-chat
- FAST_MODEL 默认为 deepseek-chat，环境变量 LLM_FAST_MODEL 可覆盖

### 会话模式
- `ConversationSession.mode`: "interview" | "normal"（默认 interview）
- 面试模式：自动意图分类（/intro /scenario /technical），注入完整知识库
- 普通模式：中性助手 prompt，非面试问题走快速模型

### 意图分类（classify_interview_intent）
- 含 "自我介绍/我是/我叫…" → /intro
- 含 "算法/代码/写一个/是什么/为什么/FastAPI/langgraph…" → /technical
- 含 "场景/STAR/怎么处理/团队/冲突…" → /scenario
- 无匹配 → 通用面试教练 prompt（完整知识库）

### 知识库注入链
```
build_profile_data_for_prompt()
  ├── 结构化简历：name, internships, projects, skills
  ├── 附件文档：profile_docs + jd_docs（usage="attach"，≤3000 字）
  └── JD 关键词：JobContext（core_skills, duties, culture_values）
```

### 模板管理
- `TemplateDefault` 表：每个 scope 一个默认模板
- 内置模板不可编辑，只能"复制副本"
- 对话时按 scope 自动加载 TemplateDefault

### Toast 通知
- `components/Toast.tsx` — Context + useToast() hook
- 右下角绿色成功/红色失败，3 秒消失
- 已接入 ProfilePage、PromptTemplatePage、SessionSelector、ConversationPage

### 提词器 (Copilot Overlay)
- Electron 透明置顶窗口（electron/overlay.html）
- 三区布局：拖拽把手 → 控制栏 → 正文（CSS pointer-events 控制穿透）
- 设置持久化：data/overlay-settings.json（位置/大小/透明度/速率/字号）
- 主窗口 📋 按钮控制开关

## 关键文件速查

| 需求 | 文件 |
|------|------|
| 对话核心 | backend/src/api/generate.py, backend/src/services/conversation_service.py |
| 前端对话页 | frontend/src/pages/ConversationPage.tsx |
| 知识库 | frontend/src/pages/ProfilePage.tsx, backend/src/services/profile_service.py |
| JD 解析 | frontend/src/pages/JDPage.tsx, backend/src/api/jd.py, backend/src/models/job_context.py |
| 模板管理 | frontend/src/pages/PromptTemplatePage.tsx, backend/src/api/templates.py |
| LLM 客户端 | backend/src/llm/client.py |
| 数据库 | backend/src/db/connection.py |
| Markdown 渲染 | frontend/src/components/MarkdownRenderer.tsx |
| 思考面板 | frontend/src/components/MessageBubble.tsx |
| SSE 流消费 | frontend/src/lib/streamConsumer.ts |
| Electron 主进程 | main.js（根目录） |
| 提词器 | electron/overlay.html, electron/overlay-preload.js |

## 安全要点

- `.env` 不在 git 中，`.env.example` 是模板
- API key 启动时延迟校验（`_ensure_key()`）
- CORS 仅允许 localhost:5173 + app://.
- 文件上传 ≤10MB，SSE 异常不泄露原始错误
- 模板导入校验 JSON 格式 + 值长度 ≤500 字符
