# 接口契约 (API Contracts)：智能面试助手

**功能**：[spec.md](../spec.md) ｜ **数据模型**：[data-model.md](../data-model.md)

后端为本地 FastAPI 服务，监听 `http://127.0.0.1:<port>`（由 Electron 主进程分配并注入前端）。所有请求/响应为 JSON（`Content-Type: application/json`），生成类接口以 **SSE（text/event-stream）** 流式返回。以下为契约概览；字段语义见数据模型。

约定：
- 成功：`2xx`，返回资源体或事件流。
- 校验失败：`422`，返回 `{ "detail": [...] }`（Pydantic 风格）。
- 业务错误：`4xx/5xx`，返回 `{ "error": { "code": "...", "message": "..." } }`。

---

## 1. 个人知识库 (Profile & Experiences) — 对应 US3 / FR-001~FR-003

### 档案
- `GET /api/profile` → 返回当前 `UserProfile`（含关联经历/技能计数）。若不存在返回 `404`。
- `POST /api/profile` → 创建档案。请求体：`{ name, phone?, email? }`。返回 `201` + 档案。
- `PUT /api/profile/{id}` → 更新基础信息。

### 实习经历
- `GET /api/experiences?type=internship` → 列表。
- `POST /api/experiences`（`type=internship`）→ 请求体：`{ company, position, start_date, end_date?, achievements[] }`。校验：`achievements` 至少 1 项。
- `PUT /api/experiences/{id}` / `DELETE /api/experiences/{id}`。

### 科研/项目经历
- `GET /api/experiences?type=project` → 列表。
- `POST /api/experiences`（`type=project`）→ 请求体：`{ project_type: research|project, name, role, tech_stack[], challenge, solution, result }`。校验：`tech_stack` 至少 1 项，`challenge/solution/result` 非空。
- `PUT /api/experiences/{id}` / `DELETE /api/experiences/{id}`。

### 技术栈
- `GET /api/skills` → 列表。
- `POST /api/skills` → 请求体：`{ category: language|framework|tool, name, proficiency }`。
- `PUT /api/skills/{id}` / `DELETE /api/skills/{id}`。

**契约测试要点**：创建后可读回；跨会话（重启后端）数据仍在（FR-002）；必填/枚举校验触发 `422`。

---

## 2. 岗位上下文 (JD Analysis) — 对应 FR-004~FR-006

- `POST /api/jd/analyze`
  - 请求体：`{ raw_text?: string, file?: (multipart) , company_intro?: string }`（文本或文件二选一）。
  - 处理：单模型结构化解析，产出 `core_skills[] / duties[] / culture_values[]`。
  - 返回 `200`：`{ id, parse_status: "success", core_skills, duties, culture_values }`。
  - 解析失败：返回 `200` + `{ parse_status: "failed" }`，并在后续生成时触发降级（不作为硬错误阻断）。
- `GET /api/jd/{id}` → 返回已解析的 JobContext。

**契约测试要点**：正常 JD → `success` 且三类字段非空；空/异常输入 → `failed`（不抛 500）。

---

## 3. 控制指令 (Directives) — 对应 FR-014 / FR-015

- `GET /api/directives?scope=self_intro|scenario` → 当前生效指令（无则返回内置默认）。
- `PUT /api/directives/{scope}` → 请求体：`{ structure_rules?, tone_rules?, fallback_angle?, is_active }`。

---

## 4. 生成 (Generation, 流式) — 对应 US1/US2 / FR-007~FR-019

### 自我介绍
- `POST /api/generate/self-intro` （SSE 流式）
  - 请求体：`{ jd_context_id?: string, directive_id?: string }`。
  - 无 `jd_context_id` 或其 `parse_status=failed` → `mode=generic_fallback`（通用模式），事件流首帧携带 `{"mode":"generic_fallback"}` 提示（FR-006）。
  - 事件流：
    - `event: meta` → `{ response_id, mode }`
    - `event: token` → `{ delta }`（逐段增量，打字机效果，FR-017 / SC-004）
    - `event: done` → `{ response_id, content, length, source_experience_ids, section_check }`
  - `section_check`：三段式结构自检结果（overview/competencies/business_fit 是否齐全，FR-007）；`length` 用于 300–400 字校验（FR-010 / SC-005）。

### 场景题/行为题
- `POST /api/generate/scenario` （SSE 流式）
  - 请求体：`{ question: string, directive_id?: string }`。
  - 事件流同上；`event: done` 额外含 `{ star_check, numbered_steps_count }`——`numbered_steps_count ≥ 3` 校验（FR-012 / SC-003），`source_experience_ids` 追溯真实经历（FR-011 / FR-013）。

### 生成历史
- `GET /api/responses?type=self_intro|scenario` → 历史列表。
- `GET /api/responses/{id}` → 单条详情（含 `source_experience_ids`、`mode`、`content`）。

**契约测试要点**：
- 首个 `token` 事件在 2s 内到达（SC-004，测试可对 LLM 打桩计时）。
- `self-intro` 的 `done.section_check` 三段齐全；`length` 落在约 300–400 字（SC-001 / SC-005）。
- `scenario` 的 `done.numbered_steps_count ≥ 3` 且 `source_experience_ids` 非空并指向真实经历（SC-003）。
- 弱匹配用例：`content` 含"角度切换"关键特征且不含编造无关工作经历（SC-002，可用断言/人工抽检）。
- 无 JD 用例：`meta.mode == "generic_fallback"`（FR-006）。

---

## 5. 文档导入与素材 (Documents) — 对应 US4 / FR-020~FR-023

- `POST /api/documents`（multipart 上传）
  - 请求：`file`（TXT/DOC/DOCX/PDF）、`scope=profile|jd`、`usage=parse|attach`。
  - `usage=parse`：提取文本并返回 `{ document_id, parse_status, proposal? }`；`proposal` 为结构化"更新建议"（见下），供用户确认。
  - `usage=attach`：仅保存原文为素材，返回 `{ document_id, parse_status }`；生成时纳入上下文。**岗位上下文的素材（如公司介绍、岗位补充材料）通过 `scope=jd` + `usage=attach` 附加**。
  - 无法提取文本（扫描件/不支持）：返回 `{ parse_status: "failed" }` 并提示改为手工录入或仅附加（不抛 500）。
- `GET /api/documents?scope=profile|jd` → 已导入/附加的文档列表。
- `DELETE /api/documents/{id}` → 删除文档及其素材关联。
- `POST /api/profile/merge`
  - 请求：`{ proposal_id, accepted_change_ids: [...] }`（用户逐项确认）。
  - 行为：仅将 `accepted_change_ids` 对应的变更写入知识库；`proposal.status → confirmed`。
  - **契约测试要点**：未在 `accepted_change_ids` 中的变更**不得写入**（FR-021 / SC-010）；冲突项在 `proposal.changes[].conflict=true` 标出。

### ProfileUpdateProposal 结构（响应片段）

```json
{
  "proposal_id": "…",
  "changes": [
    { "id": "c1", "target": "internship", "op": "add",
      "value": { "company": "…", "position": "…", "achievements": ["…"] }, "conflict": false },
    { "id": "c2", "target": "skill", "op": "update",
      "value": { "name": "Go", "proficiency": "精通" }, "conflict": true }
  ]
}
```

---

## 6. 呈现偏好 (Display Settings) — 对应 US5 / FR-024~FR-027

- `GET /api/settings/display` → `{ mode, opacity, position_x, position_y, stream_speed, auto_scroll, scroll_speed }`（无则返回默认）。
- `PUT /api/settings/display` → 更新任意子集。
  - `mode`：`inline|floating`；`opacity`：0–1，服务端**钳制到 ≥ 可读下限**（如 0.35，FR-025/SC-012）；`stream_speed`：字/秒或 `slow|normal|fast`，**生成前预设**（FR-026）；`auto_scroll`：布尔（默认开），`scroll_speed`：`slow|normal|fast`（FR-028）。
  - 偏好持久化，后续生成沿用（FR-027）。

> 说明：悬浮窗的置顶/透明/拖拽为桌面端（Electron）呈现层能力，本接口仅负责**偏好的读写与持久化**；生成内容仍复用第 4 节的 SSE 流，主面板与悬浮窗只是呈现层不同。

**契约测试要点**：`opacity` 传入低于下限的值被钳制；`PUT` 后 `GET` 可读回；`stream_speed` 变更即时影响前端打字机节流（前端断言）。

---

## 7. 会话与消息 (Sessions & Messages) — 对应 US6 / FR-029~FR-032

- `GET /api/sessions` → 当前档案下所有会话列表（按 `updated_at` 降序）。
- `POST /api/sessions` → 创建新会话。请求：`{ name, jd_context_id?, active_template_id? }`。首次启动若无会话，自动创建"默认面试准备"。
- `PUT /api/sessions/{id}` → 重命名/切换关联的 JD 或模板。
- `DELETE /api/sessions/{id}` → 删除会话及其全部消息（需确认，前端弹窗）。
- `GET /api/sessions/{id}/messages` → 该会话的消息列表（分页，`?before=<timestamp>&limit=50`）。
- 上下文滑动窗口由后端在生成服务中管理：组装 Prompt 时取"最近 N 条消息全文 + 早期消息的 LLM 摘要"，确保不被截断丢失关键事实。

**契约测试要点**：创建会话 → 列表可见；切换会话后消息历史独立；删除会话后消息级联删除。

---

## 8. 语音扩展配置 (Voice Adapters) — 对应 US7 / FR-033~FR-034

- `GET /api/voice-adapters` → 已注册的语音适配器列表及启用状态。
- `POST /api/voice-adapters` → 注册新适配器。请求：`{ name, adapter_type, enabled, settings? }`。
- `PUT /api/voice-adapters/{id}` → 更新配置或切换启用。
- `DELETE /api/voice-adapters/{id}` → 移除适配器注册。
- `GET /api/voice-adapters/active` → 返回当前启用的适配器（无则 404，前端据此控制麦克风按钮可用性）。

> 说明：语音转录的实际执行由注册的适配器插件在客户端完成，后端仅管理配置；转录文本作为普通用户输入进入后续消息/生成流程。

---

## 9. 提示词模板 (Prompt Templates) — 对应 US8 / FR-035~FR-039

- `GET /api/prompt-templates?scope=self_intro|scenario` → 模板列表（内置在前，用户在后）。
- `POST /api/prompt-templates` → 新建自定义模板。请求：`{ scope, name, structure_rules?, style_rules? }`。
- `PUT /api/prompt-templates/{id}` → 编辑模板（若 `is_builtin=true` 则自动生成副本并返回新 `id`，内置原件不变——copy-on-edit）。
- `DELETE /api/prompt-templates/{id}` → 删除模板（`is_builtin=true` 时返回 403）。
- `POST /api/prompt-templates/{id}/export` → 导出为 JSON 文件下载。
- `POST /api/prompt-templates/import` → 从 JSON 文件导入模板（冲突时生成副本并加"导入"后缀）。

**契约测试要点**：编辑内置模板返回新 ID 且原件未变；删除内置返回 403；规则冲突（如 `sections` 与段落数矛盾）保存时返回 422 并指出冲突。

---

## 10. 健康检查

- `GET /api/health` → `{ status: "ok", model: "deepseek-v4-pro" }`（供 Electron 主进程确认后端就绪后再加载前端）。
