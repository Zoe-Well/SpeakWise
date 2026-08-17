# 技术栈智能分类实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将技术栈按 8 个固定大类分组展示，并支持 LLM 对现有技能进行“预览后确认”的批量整理。

**Architecture:** 后端集中维护分类键、中文标签和合法性校验；简历解析与现有技能整理共用同一套分类定义。前端维护对应的展示顺序与文案，ProfilePage 负责触发预览和保存，独立弹窗只负责展示确认。现有 `Skill.category` 字段继续存稳定键，不新增表或迁移。

**Tech Stack:** Python 3.12、FastAPI、SQLModel、pytest、React 18、TypeScript、TanStack Query、Vitest、Testing Library。

## Global Constraints

- 分类键固定为 `programming_language`、`frontend_client`、`backend_data`、`ai_algorithm`、`agent_llm`、`cloud_devops`、`software_engineering`、`other`。
- 每项技能只能属于一个类别，未知或遗漏分类归入 `other`。
- 现有技能分类必须先预览，用户确认后才能写入数据库。
- 新简历解析复用已有 LLM 请求，不增加第二次分类调用。
- 不新增依赖、数据库表、迁移、动态分类、二级分类或自动页面加载调用。

---

### Task 1: 后端分类定义与 LLM 分类器

**Files:**

- Create: `backend/src/services/skill_categorizer.py`
- Create: `backend/tests/unit/test_skill_categorizer.py`

**Interfaces:**

- Produces: `SKILL_CATEGORIES: dict[str, str]`
- Produces: `normalize_category(value: str | None) -> str`
- Produces: `category_label(value: str | None) -> str`
- Produces: `classify_existing_skills(skills: list[dict]) -> list[dict]`

- [ ] **Step 1: 写分类合法性和 LLM 结果补齐的失败测试**

```python
def test_normalize_unknown_category_to_other():
    assert normalize_category("invented") == "other"

def test_classification_keeps_every_skill_and_normalizes_unknown(monkeypatch):
    async def fake_chat(*_args, **_kwargs):
        return '{"classifications":[{"id":1,"category":"agent_llm"},{"id":2,"category":"invented"}]}'
    monkeypatch.setattr(skill_categorizer.llm_client, "chat", fake_chat)
    result = asyncio.run(skill_categorizer.classify_existing_skills([
        {"id": 1, "name": "RAG", "category": "other"},
        {"id": 2, "name": "Docker", "category": "other"},
        {"id": 3, "name": "React", "category": "other"},
    ]))
    assert [item["suggested_category"] for item in result] == ["agent_llm", "other", "other"]
```

- [ ] **Step 2: 运行测试并确认因模块不存在而失败**

Run: `uv run pytest backend/tests/unit/test_skill_categorizer.py -q`

Expected: FAIL，提示 `backend.src.services.skill_categorizer` 不存在。

- [ ] **Step 3: 实现固定分类、JSON 解析和完整映射**

```python
SKILL_CATEGORIES = {
    "programming_language": "编程语言",
    "frontend_client": "前端与客户端",
    "backend_data": "后端与数据",
    "ai_algorithm": "AI 与算法",
    "agent_llm": "Agent 与 LLM 应用",
    "cloud_devops": "云平台与 DevOps",
    "software_engineering": "软件工程能力",
    "other": "其他",
}

def normalize_category(value: str | None) -> str:
    return value if value in SKILL_CATEGORIES else "other"

async def classify_existing_skills(skills: list[dict]) -> list[dict]:
    prompt = (
        "将技能映射到给定固定分类。只返回严格 JSON："
        '{"classifications":[{"id":1,"category":"agent_llm"}]}。'
        f"合法分类及含义：{json.dumps(SKILL_CATEGORIES, ensure_ascii=False)}。"
        f"技能：{json.dumps(skills, ensure_ascii=False)}"
    )
    raw = await llm_client.chat(
        [{"role": "user", "content": prompt}],
        temperature=0.1,
        model=llm_client.fast_model(),
    )
    if raw.strip().startswith("```"):
        raw = raw.strip().split("\n", 1)[-1].rsplit("```", 1)[0]
    data = json.loads(raw)
    suggested = {
        int(item["id"]): normalize_category(item.get("category"))
        for item in data.get("classifications", [])
        if isinstance(item, dict) and "id" in item
    }
    return [
        {
            "id": skill["id"],
            "name": skill["name"],
            "current_category": normalize_category(skill.get("category")),
            "suggested_category": suggested.get(skill["id"], "other"),
        }
        for skill in skills
    ]
```

- [ ] **Step 4: 运行测试并确认通过**

Run: `uv run pytest backend/tests/unit/test_skill_categorizer.py -q`

Expected: PASS。

- [ ] **Step 5: 提交本任务**

```powershell
git add backend/src/services/skill_categorizer.py backend/tests/unit/test_skill_categorizer.py
git commit -m "feat: add fixed skill categorizer"
```

---

### Task 2: 新简历导入使用固定类别

**Files:**

- Modify: `backend/src/api/documents.py`（`_llm_parse_resume` 提示词及技能结果规范化）
- Create: `backend/tests/unit/test_resume_skill_categories.py`

**Interfaces:**

- Consumes: `SKILL_CATEGORIES`、`normalize_category()`
- Preserves: `_llm_parse_resume(text: str) -> dict`

- [ ] **Step 1: 写导入分类规范化失败测试**

```python
def test_resume_parser_normalizes_skill_categories(monkeypatch):
    async def fake_chat(*_args, **_kwargs):
        return '{"name":"Zoe","internships":[],"projects":[],"skills":[' \
               '{"category":"agent_llm","name":"RAG","proficiency":"熟悉"},' \
               '{"category":"framework","name":"React","proficiency":"熟悉"}]}'
    monkeypatch.setattr(documents.llm_client, "chat", fake_chat)
    result = asyncio.run(documents._llm_parse_resume("resume"))
    assert [item["category"] for item in result["skills"]] == ["agent_llm", "other"]
```

- [ ] **Step 2: 运行测试并确认旧分类 `framework` 未被规范化**

Run: `uv run pytest backend/tests/unit/test_resume_skill_categories.py -q`

Expected: FAIL，实际第二项仍为 `framework`。

- [ ] **Step 3: 更新解析提示词和结果边界校验**

在提示词中列出 8 个合法键及中文语义；JSON 解析成功后遍历 `data["skills"]`，使用 `normalize_category()` 覆盖 `category`。不改变实习、项目和提案生成流程。

- [ ] **Step 4: 运行导入测试并确认通过**

Run: `uv run pytest backend/tests/unit/test_resume_skill_categories.py -q`

Expected: PASS。

- [ ] **Step 5: 提交本任务**

```powershell
git add backend/src/api/documents.py backend/tests/unit/test_resume_skill_categories.py
git commit -m "feat: categorize imported resume skills"
```

---

### Task 3: 分类预览与事务应用接口

**Files:**

- Modify: `backend/src/services/profile_service.py`
- Modify: `backend/src/api/profile.py`
- Create: `backend/tests/unit/test_profile_skill_classification.py`

**Interfaces:**

- Produces: `apply_skill_categories(session: Session, profile_id: int, assignments: list[dict]) -> list[Skill]`
- Produces: `POST /api/skills/classification/preview`，请求体 `{"skills":[{"id":1,"name":"RAG"}]}`，返回当前激活简历全部技能的预览。
- Produces: `POST /api/skills/classification/apply`，请求体 `{"assignments":[{"id":1,"category":"agent_llm"}]}`。

- [ ] **Step 1: 写预览不落库、越权 ID 拒绝、合法批量应用的失败测试**

```python
def test_preview_does_not_persist(monkeypatch, db):
    # 创建 active profile 和 category="other" 的技能；mock 分类器返回 agent_llm。
    result = asyncio.run(profile.preview_skill_classification(
        data={"skills": [{"id": skill.id, "name": skill.name}]},
        session=db,
    ))
    assert result[0]["suggested_category"] == "agent_llm"
    assert db.get(Skill, result[0]["id"]).category == "other"

def test_apply_rejects_skill_from_another_profile(db):
    with pytest.raises(ValueError):
        profile_service.apply_skill_categories(db, active_profile.id, [
            {"id": foreign_skill.id, "category": "backend_data"},
        ])
```

- [ ] **Step 2: 运行测试并确认接口/服务不存在**

Run: `uv run pytest backend/tests/unit/test_profile_skill_classification.py -q`

Expected: FAIL，提示预览端点或 `apply_skill_categories` 不存在。

- [ ] **Step 3: 实现当前简历预览和事务批量应用**

```python
def apply_skill_categories(session, profile_id, assignments):
    skills = {item.id: item for item in list_skills(session, profile_id)}
    if any(item.get("id") not in skills for item in assignments):
        raise ValueError("技能不属于当前简历")
    for assignment in assignments:
        skills[assignment["id"]].category = normalize_category(assignment.get("category"))
        session.add(skills[assignment["id"]])
    session.commit()
    return list(skills.values())
```

预览端点校验前端提交的技能 ID 集合与当前活跃简历一致，名称以数据库值为准，再调用 `classify_existing_skills()`；应用端点校验 `assignments` 为列表，捕获 `ValueError` 返回 422。LLM/JSON 异常由预览端点转换为不泄露内部响应的 502 提示。

- [ ] **Step 4: 运行接口测试并确认通过**

Run: `uv run pytest backend/tests/unit/test_profile_skill_classification.py -q`

Expected: PASS。

- [ ] **Step 5: 提交本任务**

```powershell
git add backend/src/services/profile_service.py backend/src/api/profile.py backend/tests/unit/test_profile_skill_classification.py
git commit -m "feat: preview and apply skill categories"
```

---

### Task 4: 中文类别进入对话上下文

**Files:**

- Modify: `backend/src/services/context_builder.py`
- Modify: `backend/tests/unit/test_context_builder.py`

**Interfaces:**

- Consumes: `category_label()`
- Preserves: `ContextBuilder.format_profile(profile_data: dict) -> str`

- [ ] **Step 1: 写中文类别输出失败测试**

```python
def test_profile_context_uses_skill_category_labels():
    text = ContextBuilder(None).format_profile({
        "name": "Zoe", "internships": [], "projects": [],
        "skills": [{"name": "RAG", "category": "agent_llm", "proficiency": "熟悉"}],
    })
    assert "技能-Agent 与 LLM 应用：RAG(熟悉)" in text
    assert "agent_llm" not in text
```

- [ ] **Step 2: 运行测试并确认当前输出包含内部键**

Run: `uv run pytest backend/tests/unit/test_context_builder.py -q`

Expected: FAIL，实际包含 `技能-agent_llm`。

- [ ] **Step 3: 分组时用 `category_label()` 转换显示名称**

将 `skills_by_category.setdefault(skill.get("category", "other"), [])` 的键改为 `category_label(skill.get("category"))`，其余上下文预算和截断逻辑不变。

- [ ] **Step 4: 运行上下文测试并确认通过**

Run: `uv run pytest backend/tests/unit/test_context_builder.py -q`

Expected: PASS。

- [ ] **Step 5: 提交本任务**

```powershell
git add backend/src/services/context_builder.py backend/tests/unit/test_context_builder.py
git commit -m "feat: label skill groups in prompts"
```

---

### Task 5: 前端分类常量、分组展示和手动添加

**Files:**

- Create: `frontend/src/lib/skillCategories.ts`
- Modify: `frontend/src/pages/ProfilePage.tsx`
- Create: `frontend/src/pages/ProfilePage.skills.test.tsx`

**Interfaces:**

- Produces: `SKILL_CATEGORIES: readonly {key: string; label: string}[]`
- Produces: `skillCategoryLabel(key: string) -> string`
- Produces: `groupSkillsByCategory(skills: Skill[]) -> Array<{key; label; skills}>`

- [ ] **Step 1: 写分组顺序、空组隐藏和手动添加类别的失败测试**

```tsx
it("groups skills by fixed category order and hides empty groups", async () => {
  renderProfileWithSkills([
    { id: 1, name: "RAG", category: "agent_llm", proficiency: "熟悉" },
    { id: 2, name: "React", category: "frontend_client", proficiency: "熟悉" },
  ]);
  expect(await screen.findByText("前端与客户端")).toBeInTheDocument();
  expect(screen.getByText("Agent 与 LLM 应用")).toBeInTheDocument();
  expect(screen.queryByText("后端与数据")).not.toBeInTheDocument();
});

it("posts the selected category when adding a skill", async () => {
  fireEvent.change(screen.getByLabelText("技能分类"), { target: { value: "agent_llm" } });
  fireEvent.change(screen.getByPlaceholderText("技能名"), { target: { value: "RAG" } });
  fireEvent.click(screen.getByRole("button", { name: "添加" }));
  await waitFor(() => expect(apiPost).toHaveBeenCalledWith("/api/skills", expect.objectContaining({ category: "agent_llm" })));
});
```

- [ ] **Step 2: 运行测试并确认当前页面平铺且发送 `language`**

Run: `cd frontend; npm test -- --run src/pages/ProfilePage.skills.test.tsx`

Expected: FAIL，找不到分类标题/选择框，或请求仍为 `category: "language"`。

- [ ] **Step 3: 实现前端分类定义、分组和类别选择框**

`skillCategories.ts` 按规格顺序导出 8 类；未知键在 `groupSkillsByCategory()` 中归入 `other`。ProfilePage 遍历非空分组输出标题和原有标签；`AddSkillBtn` 增加带 `aria-label="技能分类"` 的选择框，默认 `other`，提交选择的分类键。

- [ ] **Step 4: 运行页面测试并确认通过**

Run: `cd frontend; npm test -- --run src/pages/ProfilePage.skills.test.tsx`

Expected: PASS。

- [ ] **Step 5: 提交本任务**

```powershell
git add frontend/src/lib/skillCategories.ts frontend/src/pages/ProfilePage.tsx frontend/src/pages/ProfilePage.skills.test.tsx
git commit -m "feat: group skills by category"
```

---

### Task 6: AI 智能整理预览确认交互

**Files:**

- Create: `frontend/src/components/SkillClassificationDialog.tsx`
- Create: `frontend/src/components/SkillClassificationDialog.test.tsx`
- Modify: `frontend/src/pages/ProfilePage.tsx`
- Modify: `frontend/src/pages/ProfilePage.skills.test.tsx`

**Interfaces:**

- Consumes preview: `{id; name; current_category; suggested_category}[]`
- Emits: `onConfirm(assignments: {id: number; category: string}[])`
- ProfilePage calls `POST /api/skills/classification/preview` then `POST /api/skills/classification/apply`.

- [ ] **Step 1: 写预览、取消不保存和确认批量保存的失败测试**

```tsx
it("previews classifications and only persists after confirmation", async () => {
  apiPost.mockResolvedValueOnce([
    { id: 1, name: "RAG", current_category: "other", suggested_category: "agent_llm" },
  ]).mockResolvedValueOnce({ updated: 1 });
  fireEvent.click(screen.getByRole("button", { name: "AI 智能整理" }));
  await waitFor(() => expect(apiPost).toHaveBeenCalledWith(
    "/api/skills/classification/preview",
    { skills: [{ id: 1, name: "RAG" }] },
  ));
  expect(await screen.findByText("Agent 与 LLM 应用")).toBeInTheDocument();
  expect(apiPost).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "确认保存" }));
  await waitFor(() => expect(apiPost).toHaveBeenLastCalledWith(
    "/api/skills/classification/apply",
    { assignments: [{ id: 1, category: "agent_llm" }] },
  ));
});

it("does not call apply after cancelling preview", async () => {
  fireEvent.click(screen.getByRole("button", { name: "取消" }));
  expect(apiPost).not.toHaveBeenCalledWith("/api/skills/classification/apply", expect.anything());
});
```

- [ ] **Step 2: 运行测试并确认整理入口/弹窗不存在**

Run: `cd frontend; npm test -- --run src/components/SkillClassificationDialog.test.tsx src/pages/ProfilePage.skills.test.tsx`

Expected: FAIL，找不到“AI 智能整理”或“确认保存”。

- [ ] **Step 3: 实现预览弹窗及 ProfilePage 请求状态**

ProfilePage 增加 `classificationPreview` 和 `classifying` 状态；无 API Key 时复用 `ApiKeyRequiredDialog`。预览成功显示按建议类别分组的只读弹窗；确认发送完整 assignments，成功后关闭弹窗、刷新 `skills` 并显示 Toast；取消只清空本地预览。请求失败只显示错误，不修改查询缓存。

- [ ] **Step 4: 运行交互测试并确认通过**

Run: `cd frontend; npm test -- --run src/components/SkillClassificationDialog.test.tsx src/pages/ProfilePage.skills.test.tsx`

Expected: PASS。

- [ ] **Step 5: 提交本任务**

```powershell
git add frontend/src/components/SkillClassificationDialog.tsx frontend/src/components/SkillClassificationDialog.test.tsx frontend/src/pages/ProfilePage.tsx frontend/src/pages/ProfilePage.skills.test.tsx
git commit -m "feat: preview skill classification"
```

---

### Task 7: 全量验证与桌面回归

**Files:**

- Verify only; no planned production changes.

**Interfaces:**

- Verifies all interfaces produced by Tasks 1–6.

- [ ] **Step 1: 运行后端相关测试**

Run: `uv run pytest backend/tests/unit/test_skill_categorizer.py backend/tests/unit/test_resume_skill_categories.py backend/tests/unit/test_profile_skill_classification.py backend/tests/unit/test_context_builder.py -q`

Expected: 全部 PASS，0 failures。

- [ ] **Step 2: 运行全部前端测试**

Run: `cd frontend; npm test`

Expected: 全部 PASS，0 failures。

- [ ] **Step 3: 运行前端正式构建**

Run: `cd frontend; npm run build`

Expected: exit code 0。

- [ ] **Step 4: 运行差异检查**

Run: `git diff --check`

Expected: exit code 0，无空白错误。

- [ ] **Step 5: 桌面版手动回归**

启动开发前端和 Electron，确认：技术栈按大类展示；点击“AI 智能整理”先出现预览；取消后数据不变；再次预览并确认后分类持久化；切换页面再返回分类仍在。

- [ ] **Step 6: 请求代码审查并处理 Critical/Important 问题**

审查范围为本计划涉及的后端服务/API、导入提示词、上下文格式化、前端分类组件和测试。修复所有 Critical/Important 问题后重复 Steps 1–4。
