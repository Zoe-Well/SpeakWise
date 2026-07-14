# 数据模型 (Data Model)：智能面试助手

**功能**：[spec.md](./spec.md) ｜ **计划**：[plan.md](./plan.md) ｜ **存储**：本地 SQLite（`data/copilot.db`）

本文件依据规格中的 Key Entities 与功能需求，定义实体、字段、关系、校验规则与状态流转。字段类型以概念表述为主，具体列类型在实现阶段落地。

---

## 实体关系概览 (ER Overview)

```text
UserProfile 1───* Internship
            1───* Project
            1───* Skill
            1───* JobContext
            1───* ControlDirective
            1───* GeneratedResponse
            1───* SourceDocument
            1───* ProfileUpdateProposal
            1───1 DisplaySettings
            1───* ConversationSession
            1───* PromptTemplate
            1───* VoiceAdapter

ConversationSession 1───* Message              (会话含多条消息)
ConversationSession *───0..1 JobContext         (会话可关联岗位上下文)
ConversationSession *───0..1 PromptTemplate     (会话可绑定活跃模板)
GeneratedResponse   1───0..1 Message            (生成产物关联到一条助手消息)
SourceDocument      1───0..1 ProfileUpdateProposal  (解析产生的待确认更新建议)
```

单用户场景下通常仅有一个 `UserProfile`；模型仍保留 `profile_id` 外键以保持结构清晰与未来多档案扩展性。

---

## 1. UserProfile（用户档案）

代表求职者身份与基础信息。

| 字段 | 说明 | 校验 |
|------|------|------|
| `id` | 主键 | 系统生成 |
| `name` | 姓名 | 必填，非空 |
| `phone` | 联系电话 | 可选；如填写需为合法号码格式 |
| `email` | 邮箱 | 可选；如填写需为合法邮箱格式 |
| `created_at` / `updated_at` | 时间戳 | 系统维护 |

**相关需求**：FR-001、FR-002。

## 2. Internship（实习经历）

| 字段 | 说明 | 校验 |
|------|------|------|
| `id` | 主键 | 系统生成 |
| `profile_id` | 所属档案（FK → UserProfile） | 必填 |
| `company` | 公司 | 必填，非空 |
| `position` | 职位 | 必填，非空 |
| `start_date` / `end_date` | 起止时间（`duration` 可派生） | 起始必填；结束可为"至今" |
| `achievements` | 可量化成果列表（字符串数组） | 至少 1 项；鼓励含量化指标 |

**相关需求**：FR-001、FR-003（必须支持可量化成果）。

## 3. Project（科研/项目经历）

| 字段 | 说明 | 校验 |
|------|------|------|
| `id` | 主键 | 系统生成 |
| `profile_id` | 所属档案（FK → UserProfile） | 必填 |
| `type` | 类型：`research`（科研）/`project`（项目） | 必填，枚举 |
| `name` | 项目名称 | 必填，非空 |
| `role` | 担任角色 | 必填 |
| `tech_stack` | 涉及技术（字符串数组） | 至少 1 项 |
| `challenge` | 挑战/问题 | 必填 |
| `solution` | 解决方案 | 必填 |
| `result` | 结果/成效 | 必填 |

**相关需求**：FR-001、FR-003（必须支持角色/技术栈/挑战/解决方案/结果）。

## 4. Skill（技术栈）

| 字段 | 说明 | 校验 |
|------|------|------|
| `id` | 主键 | 系统生成 |
| `profile_id` | 所属档案（FK → UserProfile） | 必填 |
| `category` | 分类：`language`/`framework`/`tool` | 必填，枚举 |
| `name` | 名称（如 Python、React） | 必填，非空 |
| `proficiency` | 熟练度等级：`了解`/`熟悉`/`精通`（或 1–5 分级） | 必填，枚举 |

**相关需求**：FR-001、FR-003（必须支持按熟练度分级）。

## 5. JobContext（岗位上下文）

岗位描述与公司介绍解析后的结构化结果。

| 字段 | 说明 | 校验 |
|------|------|------|
| `id` | 主键 | 系统生成 |
| `profile_id` | 关联档案（FK，可空——通用模式无档案绑定） | 可选 |
| `raw_text` | JD/公司介绍原文（缓存于 `data/jd_cache/`） | 提供时非空 |
| `core_skills` | 核心技能要求（硬技能，字符串数组） | 解析产物 |
| `duties` | 主要岗位职责/业务场景（字符串数组） | 解析产物 |
| `culture_values` | 公司价值观/业务方向（字符串数组） | 解析产物 |
| `parse_status` | 解析状态：`pending`/`success`/`failed` | 必填 |
| `parsed_at` | 解析完成时间 | 成功后写入 |

**状态流转**：`pending → success` 或 `pending → failed`。`failed`（或 `raw_text` 缺失）时，生成流程降级为"通用面试模式"。

**相关需求**：FR-004、FR-005、FR-006。

## 6. ControlDirective（控制指令）

用户指定的"硬规则"，约束生成结构与策略。

| 字段 | 说明 | 校验 |
|------|------|------|
| `id` | 主键 | 系统生成 |
| `profile_id` | 所属档案（FK → UserProfile） | 必填 |
| `scope` | 适用场景：`self_intro`/`scenario` | 必填，枚举 |
| `structure_rules` | 结构/顺序规则（如"概述→技能→业务"） | 可选，缺省用内置默认 |
| `tone_rules` | 语气规则 | 可选 |
| `fallback_angle` | 弱匹配弥补角度（如"学习/个人实践/底层逻辑"） | 可选 |
| `is_active` | 是否启用 | 布尔 |

**相关需求**：FR-014（硬规则）、FR-015（软自适应在未约束处生效）。

## 7. GeneratedResponse（生成话术）

一次自我介绍或场景题回答的产物与其可追溯元数据。

| 字段 | 说明 | 校验 |
|------|------|------|
| `id` | 主键 | 系统生成 |
| `profile_id` | 所属档案（FK → UserProfile） | 必填 |
| `type` | 类型：`self_intro`/`scenario` | 必填，枚举 |
| `mode` | 生成模式：`customized`（定制）/`generic_fallback`（通用降级） | 必填 |
| `input_question` | 场景题问题（`scenario` 时必填） | 条件必填 |
| `jd_context_id` | 关联岗位上下文（FK，可空） | 可选 |
| `directive_id` | 本次所用控制指令（FK，可空） | 可选 |
| `content` | 生成正文（文本/Markdown） | 非空 |
| `source_experience_ids` | 引用的经历来源（Internship/Project 的 id 列表） | 支撑可追溯校验 |
| `status` | 状态：`generating`/`completed`/`error` | 必填 |
| `created_at` | 生成时间 | 系统维护 |

**状态流转**：`generating → completed` 或 `generating → error`。

**校验/业务规则**（来自需求与成功标准）：
- `type=self_intro`：`content` 须满足三段式结构（概述→技能+证据→业务匹配，FR-007）；长度约 300–400 字（FR-010 / SC-005）。
- `type=scenario`：`content` 的"行动"部分须含明确编号步骤（≥3 步，FR-012 / SC-003）。
- `source_experience_ids` 必须指向用户真实存在的经历（FR-011 / FR-013 / SC-003 可追溯）。
- 弱匹配时 `content` 须体现"角度切换"且不含编造的无关工作经历（FR-008 / FR-009 / SC-002）。

**相关需求**：FR-007 ~ FR-013、FR-016、FR-018、FR-019。

## 8. SourceDocument（来源文档）

用户导入或附加的原始文档及其提取文本。

| 字段 | 说明 | 校验 |
|------|------|------|
| `id` | 主键 | 系统生成 |
| `profile_id` | 所属档案（FK → UserProfile） | 必填 |
| `scope` | 归属范围：`profile`（知识库）/`jd`（岗位上下文） | 必填，枚举 |
| `usage` | 用途：`parse`（解析入库）/`attach`（作为素材保留） | 必填，枚举 |
| `filename` | 原始文件名 | 必填 |
| `file_type` | 类型：`txt`/`docx`/`doc`/`pdf` | 必填，枚举 |
| `extracted_text` | 提取出的文本（供注入上下文） | 解析成功后非空 |
| `parse_status` | `pending`/`success`/`failed`（如扫描件无文本层） | 必填 |
| `created_at` | 导入时间 | 系统维护 |

**状态流转**：`pending → success`（可提取文本）或 `pending → failed`（不受支持/无文本层 → 提示手工录入或仅附加）。

**相关需求**：FR-020、FR-022、FR-023。

## 9. ProfileUpdateProposal（知识库更新建议）

由文档解析产生、写入知识库前待用户确认的结构化变更集合。

| 字段 | 说明 | 校验 |
|------|------|------|
| `id` | 主键 | 系统生成 |
| `profile_id` | 所属档案（FK → UserProfile） | 必填 |
| `document_id` | 来源文档（FK → SourceDocument） | 必填 |
| `changes` | 拟变更项列表：每项含 `target`（internship/project/skill/profile 字段）、`op`（add/update）、`value`、`conflict`（是否与现有冲突） | 至少 1 项 |
| `status` | `pending`/`confirmed`/`rejected` | 必填 |
| `created_at` | 生成时间 | 系统维护 |

**状态流转**：`pending → confirmed`（用户逐项确认后写入知识库）或 `pending → rejected`（忽略）。**业务规则**：仅 `confirmed` 项允许写入知识库；禁止未经确认的自动覆盖（FR-021 / SC-010）。

**相关需求**：FR-021、FR-023。

## 10. DisplaySettings（呈现偏好）

生成结果呈现方式与悬浮窗偏好（单用户单条）。

| 字段 | 说明 | 校验 |
|------|------|------|
| `id` | 主键 | 系统生成 |
| `profile_id` | 所属档案（FK → UserProfile） | 必填 |
| `mode` | 呈现方式：`inline`（面板）/`floating`（悬浮窗） | 必填，枚举 |
| `opacity` | 悬浮窗透明度（0–1），**必须 ≥ 可读性下限**（如 0.35） | 钳制到 [下限, 1] |
| `position_x` / `position_y` | 悬浮窗屏幕坐标 | 可空（首次居中/默认） |
| `stream_speed` | 流式速率（字/秒，或 `slow`/`normal`/`fast`），**可在生成前预设** | 必填，含默认 |
| `auto_scroll` | 是否自动缓慢滚动（提词器效果） | 布尔，默认开启 |
| `scroll_speed` | 自动滚动速度（`slow`/`normal`/`fast`，或像素/秒） | 含默认 |
| `updated_at` | 更新时间 | 系统维护 |

**业务规则**：偏好被持久化并在后续生成时沿用（FR-027）；`opacity` 低于下限时钳制以保证可读（FR-025 / SC-012）；流式速率在生成前设定并作用于本次生成（FR-026）；自动滚动开关与速度随偏好持久化，生成中与生成后均可生效并可暂停（FR-028 / SC-013）。

**相关需求**：FR-024 ~ FR-028。

## 11. ConversationSession（会话）

一个独立的面试准备对话线程。

| 字段 | 说明 | 校验 |
|------|------|------|
| `id` | 主键 | 系统生成 |
| `profile_id` | 所属档案（FK → UserProfile） | 必填 |
| `name` | 会话名称（如"腾讯面试准备"） | 必填，非空 |
| `jd_context_id` | 关联岗位上下文（FK → JobContext，可空） | 可选 |
| `active_template_id` | 当前活跃提示词模板（FK → PromptTemplate，可空，缺省使用内置默认） | 可选 |
| `created_at` / `updated_at` | 时间戳 | 系统维护 |

**业务规则**：首次启动自动创建"默认面试准备"会话；删除会话同时删除其所有消息（需确认）。

## 12. Message（消息）

会话中的一条对话记录。

| 字段 | 说明 | 校验 |
|------|------|------|
| `id` | 主键 | 系统生成 |
| `session_id` | 所属会话（FK → ConversationSession） | 必填 |
| `role` | `user`（用户提问）/`assistant`（系统回答） | 必填，枚举 |
| `command` | 触发的斜杠命令：`/intro`/`/scenario`/`/followup`/`null`（普通文本） | 可空 |
| `content` | 消息文本（对于斜杠命令，存储解析后的参数：`/intro` 含要求文本、`/scenario` 含问题文本） | 必填 |
| `type` | 消息类型：`self_intro`/`scenario`/`follow_up`/`system`/`free_text` | 必填，枚举 |
| `response_id` | 关联生成产物（FK → GeneratedResponse，`role=assistant` 时可空） | 可选 |
| `source_experience_ids` | 本次引用的经历（ID 列表，可追溯） | 可选 |
| `created_at` | 时间戳 | 系统维护 |

**业务规则**：消息按 `created_at` 排序；上下文管理以最近 N 条消息 + 关键事实摘要的滑动窗口运行。

## 13. PromptTemplate（提示词模板）

可管理、可编辑的生成配方。

| 字段 | 说明 | 校验 |
|------|------|------|
| `id` | 主键 | 系统生成 |
| `profile_id` | 所属档案（FK → UserProfile） | 必填 |
| `scope` | 适用范围：`self_intro`/`scenario` | 必填，枚举 |
| `name` | 模板名称 | 必填，非空 |
| `structure_rules` | 结构规则（如 `{"sections":["概述","技能+证据","业务匹配"],"step_min":3}`） | JSON，可为空 |
| `style_rules` | 风格规则（如 `{"tone":"沉稳","length_target":"300-400","fallback_angle":"学习角度"}`） | JSON，可为空 |
| `is_builtin` | 是否内置默认模板 | 布尔，默认 false |
| `created_at` / `updated_at` | 时间戳 | 系统维护 |

**业务规则**：内置模板 `is_builtin=true` 不可删除/覆盖——编辑时自动生成副本；用户模板可自由编辑/删除；支持导出/导入为 JSON 文件。

## 14. VoiceAdapter（语音扩展配置）

语音识别的扩展注册信息。

| 字段 | 说明 | 校验 |
|------|------|------|
| `id` | 主键 | 系统生成 |
| `profile_id` | 所属档案（FK → UserProfile） | 必填 |
| `name` | 显示名称 | 必填 |
| `adapter_type` | 适配器类型标识符（如 `web-speech-api`、`whisper-local`、`cloud-asr`） | 必填 |
| `enabled` | 是否启用 | 布尔 |
| `settings` | 配置参数（JSON blob，如 API 端点、模型名等） | 可空 JSON |
| `created_at` | 注册时间 | 系统维护 |

**业务规则**：无已启用适配器时，UI 语音按钮禁用并提示；多个适配器可并存但同时只有一个启用。

---

## 派生/可选：向量索引（RAG，后续）

> MVP 不落地。当引入 Pgvector 时，为 `Internship`/`Project` 的文本片段生成嵌入，存于向量表（`experience_chunk_embeddings`），作为可从 SQLite 重建的**派生索引**，用于上下文超长时的语义检索。详见 [research.md](./research.md) §4。
