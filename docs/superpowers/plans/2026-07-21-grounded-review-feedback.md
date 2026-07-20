# Grounded Review and Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让简历评审和岗位分析只基于可追溯证据输出，阻止虚构联系方式、技术经历和量化结果；同时为错误路由提供用户可见的纠正与再生成闭环，并保留不泄露正文的本地诊断信息。

**Architecture:** `ReviewEvidenceBundle` 将结构化资料、附件和 JD 切成带 id 的事实证据；prompt 强制区分确认事实、缺失项和建议，生成后再经过确定性 claim validator。路由纠正保存为独立 feedback 记录，并以 `user_override` 重新生成。请求诊断只保存事件计数、耗时、路由与错误码。

**Tech Stack:** FastAPI, Pydantic 2, SQLModel, SQLite, pytest, React, TypeScript, Vitest, Testing Library

## Global Constraints

- 不存在于 evidence bundle 的联系方式、数字结果、技术经历不得写成用户事实。
- 缺失信息统一使用 `[待补充：字段]`，建议必须以“建议”语气表达。
- validator 只标记和降级不可信 claim，不静默编造替代内容。
- 纠错必须保留原始消息和原始路由，不能覆盖审计历史。
- 诊断日志不得保存简历正文、JD 正文、完整 prompt、API key 或模型原始异常。
- 自动测试全部使用 fake LLM；真实 API 仅用于最后人工冒烟。

---

## Task 1: 建立可追溯评审证据模型

**Files:**

- Create: `backend/src/models/review_evidence.py`
- Create: `backend/src/services/review_evidence.py`
- Create: `backend/tests/unit/test_review_evidence.py`

- [ ] **Step 1: 写失败测试固定证据 id 和来源**

```python
bundle = build_review_evidence(profile, jd, documents)
assert bundle.items[0].evidence_id.startswith("profile:")
assert {item.source_type for item in bundle.items} <= {"profile", "project", "skill", "document", "jd"}
assert bundle.render_for_prompt().count(bundle.items[0].evidence_id) == 1
```

覆盖空资料、重复技能去重、附件裁剪、相同输入产生相同 id。

- [ ] **Step 2: 运行并确认模块不存在**

Run: `uv run pytest backend/tests/unit/test_review_evidence.py -q`

Expected: import failure。

- [ ] **Step 3: 实现 evidence 类型和 builder**

```python
class EvidenceItem(BaseModel):
    evidence_id: str
    source_type: Literal["profile", "project", "skill", "document", "jd"]
    source_id: str
    field: str
    value: str

class ReviewEvidenceBundle(BaseModel):
    items: list[EvidenceItem]
    missing_fields: list[str]
```

`ReviewEvidenceBundle` 另提供 `render_for_prompt(self) -> str`，按 `evidence_id` 排序后每行输出一个证据项。

id 格式固定为 `<source_type>:<source_id>:<field>`；附件长文本按阶段二预算器裁剪，不生成随机 id。

- [ ] **Step 4: 验证并提交**

Run: `uv run pytest backend/tests/unit/test_review_evidence.py -q`

Expected: all passed。

```powershell
git add backend/src/models/review_evidence.py backend/src/services/review_evidence.py backend/tests/unit/test_review_evidence.py
git commit -m "feat: build traceable review evidence"
```

## Task 2: 重写 grounded 评审与岗位分析 prompt

**Files:**

- Modify: `backend/src/prompts/resume_review.py`
- Modify: `backend/src/prompts/job_analysis.py`
- Create: `backend/tests/unit/test_grounded_review_prompts.py`

- [ ] **Step 1: 写 prompt 合同失败测试**

断言 prompt 明确包含以下合同：

- 事实陈述需附 `[evidence_id]`。
- 未提供的数据写 `[待补充：字段名]`。
- 不得推测电话、邮箱、公司、技术栈、规模和百分比。
- 量化建议用占位结构，不得把示例数字当事实。
- 输出分为“已确认问题 / 待补充信息 / 优化建议”。

同时断言删除“量化一切可量化内容”及带具体虚构数字的替换示例。

- [ ] **Step 2: 运行并确认当前 prompt 违反合同**

Run: `uv run pytest backend/tests/unit/test_grounded_review_prompts.py -q`

Expected: required clauses missing 或 forbidden phrase present。

- [ ] **Step 3: 重写 prompt builder**

prompt 接收 `ReviewEvidenceBundle.render_for_prompt()`，不再接收无来源的松散 profile dict。输出中的建议模板使用如“将延迟从 `[待补充：优化前]` 降至 `[待补充：优化后]`”。

- [ ] **Step 4: 验证并提交**

Run: `uv run pytest backend/tests/unit/test_grounded_review_prompts.py -q`

Expected: all passed。

```powershell
git add backend/src/prompts/resume_review.py backend/src/prompts/job_analysis.py backend/tests/unit/test_grounded_review_prompts.py
git commit -m "fix: ground review prompts in supplied evidence"
```

## Task 3: 实现不可信 claim 检测器

**Files:**

- Create: `backend/src/services/review_claim_validator.py`
- Create: `backend/tests/unit/test_review_claim_validator.py`

- [ ] **Step 1: 写失败测试覆盖三类高风险 claim**

覆盖未支持的手机号/邮箱、百分比与金额、证据中不存在的技术名。允许 evidence 已包含的值、Markdown 序号、年份以及 `[待补充]` 占位符。

```python
result = validate_review_claims("性能提升 40%，使用了 LangGraph", bundle_without_them)
assert {issue.kind for issue in result.issues} == {"unsupported_number", "unsupported_technology"}
assert result.safe is False
```

- [ ] **Step 2: 运行并确认模块不存在**

Run: `uv run pytest backend/tests/unit/test_review_claim_validator.py -q`

Expected: import failure。

- [ ] **Step 3: 实现确定性 validator**

```python
class ClaimIssue(BaseModel):
    kind: Literal["unsupported_contact", "unsupported_number", "unsupported_technology", "unknown_evidence"]
    excerpt: str

class ValidationResult(BaseModel):
    safe: bool
    issues: list[ClaimIssue]
    sanitized_content: str
```

电话号码、邮箱、带单位数值用规则检测；技术词来自项目技能词典与 evidence token 集合。对不可信片段替换为 `[待补充：请确认原始信息]`，并保留 issue 供 UI 提示。

- [ ] **Step 4: 验证并提交**

Run: `uv run pytest backend/tests/unit/test_review_claim_validator.py -q`

Expected: all passed。

```powershell
git add backend/src/services/review_claim_validator.py backend/tests/unit/test_review_claim_validator.py
git commit -m "feat: detect unsupported review claims"
```

## Task 4: 将证据与 validator 接入评审流

**Files:**

- Modify: `backend/src/api/review.py`
- Modify: `backend/src/llm/streaming.py`
- Create: `backend/tests/integration/test_grounded_review_api.py`

- [ ] **Step 1: 写 fake LLM 集成失败测试**

fake 输出不存在的手机号、`提升 40%` 和 `LangGraph`。断言 token 流仍可到达，但最终 `done.content` 已安全降级，`done` 额外返回 `validation_issues`，没有虚构内容；合法 evidence claim 原样保留。

- [ ] **Step 2: 运行并确认当前接口原样返回虚构内容**

Run: `uv run pytest backend/tests/integration/test_grounded_review_api.py -q`

Expected: fabricated text still present。

- [ ] **Step 3: 接入 evidence bundle 和完成态校验**

评审开始时创建 bundle；模型流式 token 可展示，但完成时对完整文本校验。若存在 issue，`done.content` 使用 sanitized content，并带：

```json
{"validation_issues":[{"kind":"unsupported_number","message":"发现未经资料支持的数字，已标记为待补充"}]}
```

不得向前端返回原始敏感 excerpt。

- [ ] **Step 4: 前端状态兼容性要求**

阶段一已规定 `done.content` 为权威内容，因此不新增特殊传输逻辑；只需扩展 done payload 类型允许 `validation_issues`。

- [ ] **Step 5: 验证并提交**

Run: `uv run pytest backend/tests/integration/test_grounded_review_api.py -q`

Expected: all passed。

Run: `uv run pytest backend/tests -q`

Expected: all passed。

```powershell
git add backend/src/api/review.py backend/src/llm/streaming.py backend/tests/integration/test_grounded_review_api.py
git commit -m "fix: validate review output before completion"
```

## Task 5: 在评审页呈现事实边界

**Files:**

- Modify: `frontend/src/pages/ReviewPage.tsx`
- Create: `frontend/src/components/ReviewValidationNotice.tsx`
- Create: `frontend/src/components/ReviewValidationNotice.test.tsx`

- [ ] **Step 1: 写失败组件测试**

断言有 issue 时显示简洁提示和 issue 数量，不显示敏感 excerpt；无 issue 时不渲染提示。

- [ ] **Step 2: 实现提示组件并接入 done 事件**

提示文案：“已将 2 处未经资料支持的内容标记为待补充。”允许展开查看类型（联系方式/数字/技术），不展示模型原文。

- [ ] **Step 3: 验证并提交**

Run: `npm test -- src/components/ReviewValidationNotice.test.tsx`

Workdir: `frontend`

Expected: all passed。

Run: `npm run build`

Expected: build succeeded。

```powershell
git add frontend/src/pages/ReviewPage.tsx frontend/src/components/ReviewValidationNotice.tsx frontend/src/components/ReviewValidationNotice.test.tsx
git commit -m "feat: explain grounded review corrections"
```

## Task 6: 保存路由纠错反馈并支持 override 再生成

**Files:**

- Create: `backend/src/models/route_feedback.py`
- Modify: `backend/src/db/connection.py`
- Create: `backend/src/services/route_feedback_service.py`
- Modify: `backend/src/api/generate.py`
- Create: `backend/tests/integration/test_route_correction.py`

- [ ] **Step 1: 写失败集成测试**

提交原消息 id、新 `topic_intent/dialogue_act`，断言：原消息路由不变；新增 feedback 指向原路由与 override；再生成使用 `source=user_override`；新助手消息与原助手消息可区分。

- [ ] **Step 2: 运行并确认 endpoint/model 不存在**

Run: `uv run pytest backend/tests/integration/test_route_correction.py -q`

Expected: 404 或 import failure。

- [ ] **Step 3: 实现 feedback 表和幂等迁移**

字段：`id`、`session_id`、`user_message_id`、`assistant_message_id`、`original_topic`、`original_act`、`corrected_topic`、`corrected_act`、`created_at`。不保存重复正文。

- [ ] **Step 4: 实现纠错接口**

新增 `POST /api/generate/correct-route`：校验消息属于 session；构造 `RoutingDecision(source="user_override", confidence=1.0)`；复用阶段二 context builder 与阶段一 SSE 返回再生成结果。错误码使用 `INVALID_ROUTE_OVERRIDE` / `MESSAGE_NOT_FOUND`。

- [ ] **Step 5: 验证并提交**

Run: `uv run pytest backend/tests/integration/test_route_correction.py -q`

Expected: all passed。

```powershell
git add backend/src/models/route_feedback.py backend/src/db/connection.py backend/src/services/route_feedback_service.py backend/src/api/generate.py backend/tests/integration/test_route_correction.py
git commit -m "feat: persist route corrections and regenerate"
```

## Task 7: 增加“分类不对”前端纠错体验

**Files:**

- Modify: `frontend/src/components/MessageBubble.tsx`
- Create: `frontend/src/components/RouteCorrectionMenu.tsx`
- Create: `frontend/src/components/RouteCorrectionMenu.test.tsx`
- Modify: `frontend/src/pages/ConversationPage.tsx`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: 写交互失败测试**

点击“分类不对”后可选择主题和行为；确认后调用一次 correction API；生成中禁用重复提交；成功后保留原回答并追加“已按新分类重新生成”的新回答。

- [ ] **Step 2: 实现最小纠错菜单**

默认预选当前标签，主题中文显示“自我介绍/场景题/技术题/职业问题/通用”，行为显示“新问题/继续追问/澄清/改写/让面试官追问”。不向用户展示 confidence 和内部 source。

- [ ] **Step 3: 接入统一流消费者**

correction API 复用阶段一状态机；原消息和原答案不修改，新答案显示 override 标签。失败使用现有 Toast，并允许重试。

- [ ] **Step 4: 验证并提交**

Run: `npm test -- src/components/RouteCorrectionMenu.test.tsx`

Workdir: `frontend`

Expected: all passed。

Run: `npm run build`

Expected: build succeeded。

```powershell
git add frontend/src/components/MessageBubble.tsx frontend/src/components/RouteCorrectionMenu.tsx frontend/src/components/RouteCorrectionMenu.test.tsx frontend/src/pages/ConversationPage.tsx frontend/src/lib/api.ts
git commit -m "feat: let users correct conversation routing"
```

## Task 8: 统一错误码与本地无敏感诊断

**Files:**

- Create: `backend/src/models/diagnostics.py`
- Create: `backend/src/services/request_diagnostics.py`
- Modify: `backend/src/db/connection.py`
- Modify: `backend/src/api/generate.py`
- Modify: `backend/src/api/review.py`
- Modify: `backend/src/api/interview.py`
- Create: `backend/tests/unit/test_request_diagnostics.py`

- [ ] **Step 1: 写失败测试证明敏感内容不会入库**

传入含 email、电话、API key 样式字符串和正文的异常，断言存储记录只有 request id、endpoint、phase、event counts、duration、route labels、error code、timestamp；不存在 raw error/prompt/content 字段。

- [ ] **Step 2: 实现诊断记录器**

接口：

```python
with RequestDiagnostics(endpoint, session_id) as diag:
    diag.set_route(decision)
    diag.record_event("token")
    diag.fail("UPSTREAM_FAILED")
```

可使用独立 SQLite 表或结构化本地日志；默认保留最近 500 条。若使用表，迁移需幂等。禁止记录 token 文本。

- [ ] **Step 3: 接入三个流 API**

统一错误码至少包含 `INVALID_REQUEST`、`RATE_LIMITED`、`REQUEST_IN_PROGRESS`、`PROTOCOL_ERROR`、`UPSTREAM_FAILED`、`INTERRUPTED`、`INVALID_ROUTE_OVERRIDE`。用户消息继续使用简洁中文。

- [ ] **Step 4: 验证并提交**

Run: `uv run pytest backend/tests/unit/test_request_diagnostics.py -q`

Expected: all passed。

Run: `uv run pytest backend/tests -q`

Expected: all passed。

```powershell
git add backend/src/models/diagnostics.py backend/src/services/request_diagnostics.py backend/src/db/connection.py backend/src/api/generate.py backend/src/api/review.py backend/src/api/interview.py backend/tests/unit/test_request_diagnostics.py
git commit -m "feat: add privacy-safe local request diagnostics"
```

## Task 9: 建立跨阶段 fake LLM 端到端回归

**Files:**

- Create: `backend/tests/fakes/fake_llm.py`
- Create: `backend/tests/e2e/test_conversation_experience.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: 实现可脚本化 fake LLM**

支持配置分类 JSON、thinking chunks、token chunks、完成、超时和中途异常，并记录收到的 messages/settings。fake 不使用网络。

- [ ] **Step 2: 写三条关键用户旅程**

1. 技术问题 → 结构化 SSE → done 内容一致 → 保存正确 route。
2. “继续追问” → 继承技术主题 → 当前消息无重复 → pro 模型。
3. 简历评审 fake 虚构数字 → validator 标记 → done 返回安全内容。

- [ ] **Step 3: 加入纠错旅程**

错误分类 → POST correction → 原回答保留 → override 回答新增 → feedback 可查询。

- [ ] **Step 4: 运行回归**

Run: `uv run pytest backend/tests/e2e/test_conversation_experience.py -q`

Expected: all passed，无外部网络访问。

- [ ] **Step 5: 提交**

```powershell
git add backend/tests/fakes/fake_llm.py backend/tests/e2e/test_conversation_experience.py backend/tests/conftest.py
git commit -m "test: cover grounded conversation journeys"
```

## Task 10: 阶段三与全项目验收

- [ ] 运行 `uv run pytest backend/tests -q`，预期全绿。
- [ ] 在 `frontend` 运行 `npm test`，预期全绿。
- [ ] 在 `frontend` 运行 `npm run build`，预期成功。
- [ ] 使用测试资料人工验证评审不再捏造电话、邮箱、百分比或未出现技术。
- [ ] 人工验证 `[待补充]` 与“优化建议”视觉区分清晰。
- [ ] 人工验证错误分类可在两次点击内纠正，原回答仍可查看。
- [ ] 检查诊断表/日志不含正文：按字段名和一条真实失败记录双重确认。
- [ ] 搜索禁用语句：`rg "量化一切|随便补充|假设用户" backend/src/prompts`，预期无命中。
- [ ] 更新设计文档三阶段验收状态和真实测试结果。
- [ ] 提交最终验收记录：`git commit -m "docs: record conversation upgrade verification"`。
