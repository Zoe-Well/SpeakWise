<!--
Sync Impact Report
==================
Version change: 未版本化模板 → 1.0.0（初始批准：占位符 → 具体条款）
Bump rationale: 首次将模板落地为具体宪法，确立完整原则集与治理规则，按语义化版本作为基线 MAJOR=1.0.0。

Modified principles (占位符 → 具体命名):
- [PRINCIPLE_1_NAME] → I. 事实锚定，绝不穿帮 (Fact-Grounded, No Fabrication) — NON-NEGOTIABLE
- [PRINCIPLE_2_NAME] → II. 双轨控制：硬规则优先，软自适应补位 (Dual-Track Control)
- [PRINCIPLE_3_NAME] → III. 数据私有化，单用户本地优先 (Privacy-First, Local Single-User)
- [PRINCIPLE_4_NAME] → IV. 可度量、可验证、可复现 (Measurable, Verifiable, Reproducible)
- [PRINCIPLE_5_NAME] → V. 规格驱动开发 (Spec-Driven Development)

Added sections:
- [SECTION_2_NAME] → 质量与安全约束 (Quality & Safety Constraints)
- [SECTION_3_NAME] → 开发工作流与质量门禁 (Development Workflow & Quality Gates)

Removed sections: 无

Templates alignment:
- ✅ .specify/templates/plan-template.md（已含 Constitution Check 门禁，与本宪法一致）
- ✅ .specify/templates/spec-template.md（宪法未新增/移除强制章节，无需改动）
- ✅ .specify/templates/tasks-template.md（按用户故事组织，契合"规格驱动/独立可测"原则）
- ✅ CLAUDE.md（已指向当前计划，作为运行期指引）

Follow-up TODOs / 待人工处理:
- ⚠ specs/001-interview-copilot/plan.md 的"宪法检查"章节仍描述宪法为"模板占位符、无门禁"，现已过时；
  建议在下次 /speckit-plan 或手动刷新时更新为引用本 1.0.0 宪法进行门禁评估。
-->

# SpeakWise（智能面试助手 Interview Copilot）Constitution

## 核心原则 (Core Principles)

### I. 事实锚定，绝不穿帮 (Fact-Grounded, No Fabrication) — NON-NEGOTIABLE

所有生成的话术**必须**可追溯到用户真实录入的经历（以 `source_experience_ids` 关联到具体的
实习/项目/技能记录）。系统**禁止**编造与用户无关的工作经历，**禁止**引入用户技术栈之外、
毫无关联的技术。当用户经历与目标岗位匹配度低时，**必须**采用"角度切换"（学习积累 /
个人实践 / 底层逻辑）进行弥补，而**不得**以虚构经历填补。

**理由**：面试助手一旦导致用户在真实面试中"穿帮"，将直接损害用户利益与信任，是本产品
不可接受的失败模式。该原则优先级高于任何流利度或说服力目标。

### II. 双轨控制：硬规则优先，软自适应补位 (Dual-Track Control)

用户以控制指令给出的**硬规则**（结构、顺序、策略）**必须**被严格遵循；模型**仅可**在用户
未约束的部分进行**软自适应**（如按问题严肃程度调整语气）。关键结构**必须**由 Prompt 约束
叠加程序校验双重保证：自我介绍固定三段式（概述 → 技能+证据 → 业务匹配）；场景题回答的
"行动"部分**必须**包含明确编号步骤（≥ 3 步）。

**理由**：可预测、可掌控的输出才能被用户信任并按需调整；纯模型自由发挥无法满足面试话术
对结构与稳定性的刚性要求。

### III. 数据私有化，单用户本地优先 (Privacy-First, Local Single-User)

个人经历数据**必须**以单用户、私有化方式本地存储，仅本人可见。用户**必须**能随时查看、
编辑、删除其数据。除生成所必需的 LLM 调用外，系统**禁止**在未经用户明确同意的情况下将
个人数据传输至任何外部服务。

**理由**：简历与经历属于敏感个人数据；隐私与用户对数据的完全掌控是产品的底线承诺。

### IV. 可度量、可验证、可复现 (Measurable, Verifiable, Reproducible)

每一条功能需求**必须**对应可度量的验收标准（SC-xxx）。对相同输入（Profile + JD + 控制指令），
系统**必须**保持核心事实一致（引用经历、数据、匹配点不自相矛盾；生成温度建议 0.3–0.5）。
输出**必须**可通过结构 / 长度 / 流利度的程序化校验；依赖 LLM 的测试**必须**对模型响应打桩
以保证确定性。

**理由**：质量必须可检验而非凭感觉；确定性测试是持续迭代不回退的前提。

### V. 规格驱动开发 (Spec-Driven Development)

开发**必须**遵循 `spec → plan → tasks → implement` 流程。规格（spec）**必须**保持实现无关
（只描述 WHAT/WHY），技术决策归于 plan/research。任何范围或行为的变更**必须**先更新规格，
再向下游（plan、tasks、代码）传播。每个用户故事**应**保持独立可实现、独立可测，作为可交付
的 MVP 增量。

**理由**：单一真源与可审计的流程，避免需求漂移与文档/代码脱节。

## 质量与安全约束 (Quality & Safety Constraints)

- **性能**：生成首字延迟**必须** < 2s；完整话术生成**必须** < 15s（SC-004）。
- **输出规格**：自我介绍长度**应**落在约 300–400 字（1–2 分钟朗读，SC-005）；场景题"行动"
  部分**必须** ≥ 3 个编号步骤（SC-003）。
- **语言**：生成内容与项目文档默认使用**中文**。
- **定位边界**：本产品为面试前准备与面试中即时参考的**文本**工具；语音识别、实时转录、
  音频处理**不在**范围内。
- **模型接入**：全流程使用**单一模型（DeepSeek-V4-Pro）**，且**必须**经由后端 `llm/` 抽象层
  调用，保证模型可配置替换；不得在业务代码中硬编码具体模型调用。
- **降级**：JD 解析失败或缺失时，系统**必须**降级为"通用面试模式"并向用户明确提示（FR-006）。
- **辅助定位**：生成结果为辅助建议，最终由用户自行判断、编辑与采用。

## 开发工作流与质量门禁 (Development Workflow & Quality Gates)

- **流程门禁**：plan 的"宪法检查"**必须**在 Phase 0 前与 Phase 1 设计后各评估一次，确认
  设计不违反本宪法各原则。
- **Prompt 治理**：分层 Prompt（`SYSTEM_ROLE / USER_CONTROL / DYNAMIC_CONTEXT`）**必须**版本化
  （如 `self_intro_v1`），"硬规则"固化并纳入版本控制。
- **测试门禁**：对外接口**必须**有契约测试；生成流程**必须**有集成测试（LLM 打桩）；结构/长度/
  编号步骤/可追溯性等业务规则**必须**有单元测试覆盖。
- **可追溯性**：每个任务以 `[USx]` 标签映射到用户故事，保证需求—任务—代码可追溯。
- **复杂度**：任何超出既定技术栈的复杂度**必须**在 plan 的"复杂度追踪"中说明理由与更简替代
  被否决的原因。
- **提交纪律**：**应**在每个任务或逻辑分组完成后提交。

## 治理 (Governance)

本宪法的效力**高于**其他一切开发实践；发生冲突时以本宪法为准。

- **修订程序**：任何修订**必须**经由 spec-kit 工作流提出、在本文件中记录，并按语义化版本
  更新版本号——MAJOR（不兼容的治理/原则移除或重定义）、MINOR（新增原则/章节或实质性
  扩展）、PATCH（措辞澄清、纠错等非语义调整）。
- **合规审查**：所有计划评审与代码评审**必须**核验对本宪法的遵循；违规项**必须**被修正或
  在"复杂度追踪"中获得明确辩护。
- **运行期指引**：日常开发以 `CLAUDE.md` 及当前活动计划（`specs/001-interview-copilot/plan.md`）
  作为运行期指引。

**Version**: 1.0.0 | **Ratified**: 2026-07-10 | **Last Amended**: 2026-07-10
