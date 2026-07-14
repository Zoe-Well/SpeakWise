"""对话服务：斜杠命令路由 + 上下文组装 + 生成编排"""

import json
from typing import AsyncIterator

from sqlmodel import Session
from backend.src.llm.client import llm_client, StreamChunk, FAST_MODEL
from backend.src.prompts.self_intro import build_intro_messages
from backend.src.prompts.scenario import build_scenario_messages
from backend.src.prompts.technical import build_technical_messages
from backend.src.services import profile_service, session_service


async def _split_thinking_stream(raw_stream: AsyncIterator[str]) -> AsyncIterator[StreamChunk]:
    """实时分割 LLM 流：遇到 '---' 之前为 thinking，之后为 token。

    作为非 reasoning 模型的兜底方案。reasoning 模型优先使用原生
    delta.reasoning_content，不需要此函数。
    """
    buffer = ""
    split_found = False

    async for token in raw_stream:
        buffer += token

        if not split_found and "---" in buffer:
            idx = buffer.index("---")
            pre = buffer[:idx].strip()
            rest = buffer[idx + 3:]

            if pre:
                yield {"type": "thinking", "content": pre}

            buffer = rest
            split_found = True
            continue

        if split_found:
            if buffer:
                yield {"type": "token", "content": buffer}
                buffer = ""

    # Flush remaining
    if buffer.strip():
        if split_found:
            yield {"type": "token", "content": buffer.strip()}
        else:
            yield {"type": "thinking", "content": buffer.strip()}


# ── 面试相关性分类 ────────────────────────────────────────────

# 面试/求职相关关键词（中英双语）
_INTERVIEW_KEYWORDS = [
    "面试", "自我介绍", "简历", "岗位", "求职", "招聘", "JD", "STAR",
    "实习", "项目经历", "技能", "职业", "跳槽", "薪资", "offer",
    "interview", "resume", "CV", "job", "career", "self-intro",
    "behavioral question", "technical interview", "coding interview",
    "自我介绍", "场景题", "追问", "/intro", "/scenario", "/followup",
    "打磨回答", "面试官", "面试问题", "模拟面试", "面经",
]


def classify_message(content: str) -> tuple[bool, str]:
    """判断消息是否与面试/求职相关。

    返回 (is_interview_related, model_to_use)。
    """
    text_lower = content.lower()
    for kw in _INTERVIEW_KEYWORDS:
        if kw.lower() in text_lower:
            return True, llm_client.model  # 使用默认 pro 模型
    return False, FAST_MODEL


# ── 面试模式下的意图分类 ────────────────────────────────────

# 自我介绍关键词
_INTRO_KEYWORDS = ["自我介绍", "介绍自己", "个人介绍", "self intro", "introduce yourself",
                    "概述", "我是", "我叫", "我的经历"]
# 技术题关键词
_TECH_KEYWORDS = ["算法", "数据结构", "代码", "编程", "leetcode", "系统设计",
                   "写一个", "实现", "复杂度", "设计模式", "架构", "SQL", "数据库",
                   "算法题", "编程题", "coding", "code", "system design",
                   "时间复杂度", "react", "vue", "python函数", "java类",
                   "手写", "八股", "原理", "底层", "网络协议", "操作系统",
                   "是什么", "为什么", "怎么用", "区别", "对比", "优缺点",
                   "fastapi", "django", "flask", "langgraph", "langchain",
                   "docker", "kubernetes", "redis", "mongodb", "postgresql",
                   "什么是", "如何", "解释", "定义", "概念"]
# 场景题关键词
_SCENARIO_KEYWORDS = ["场景", "STAR", "情景", "项目经历", "行为面试", "behavioral",
                       "遇到", "怎么处理", "如何解决", "说说你", "讲一个", "举例",
                       "案例", "冲突", "失败", "挑战", "团队", "领导", "沟通"]


def classify_interview_intent(content: str) -> str | None:
    """在面试模式下自动识别用户意图，返回命令类型。

    返回: "/intro" | "/scenario" | "/technical" | None（通用问答）
    """
    text_lower = content.lower()

    # Check explicit slash commands first
    if text_lower.startswith("/intro"):
        return "/intro"
    if text_lower.startswith("/scenario"):
        return "/scenario"
    if text_lower.startswith("/technical"):
        return "/technical"
    if text_lower.startswith("/followup"):
        return "/followup"

    # Keyword scoring
    intro_score = sum(1 for kw in _INTRO_KEYWORDS if kw.lower() in text_lower)
    tech_score = sum(1 for kw in _TECH_KEYWORDS if kw.lower() in text_lower)
    scenario_score = sum(1 for kw in _SCENARIO_KEYWORDS if kw.lower() in text_lower)

    # Need at least 1 keyword match to classify
    if tech_score > 0 and tech_score >= intro_score and tech_score >= scenario_score:
        return "/technical"
    if scenario_score > 0 and scenario_score >= intro_score:
        return "/scenario"
    if intro_score > 0:
        return "/intro"

    # No clear match → generic interview response (full context, no template)
    return None


async def _native_thinking_stream(
    messages: list[dict], temperature: float = 0.4, model: str | None = None
) -> AsyncIterator[StreamChunk]:
    """使用 LLM 原生 reasoning 能力的流，直接透传 structured chunks。"""
    async for chunk in llm_client.stream(messages, temperature=temperature, model=model):
        yield chunk


def _load_template_for_scope(db, scope: str) -> dict | None:
    """从 TemplateDefault 加载某 scope 的默认模板规则。"""
    if not db:
        return None
    from backend.src.models.template import PromptTemplate, TemplateDefault
    from sqlmodel import select as _sel
    from backend.src.services import profile_service

    profile = profile_service.get_or_create_profile(db)
    default = db.exec(
        _sel(TemplateDefault).where(
            TemplateDefault.profile_id == profile.id,
            TemplateDefault.scope == scope,
        )
    ).first()
    template_id = default.template_id if default else None
    if not template_id:
        return None
    t = db.get(PromptTemplate, template_id)
    if not t:
        return None
    return _parse_template_rules(t)


def _load_template(db, template_id: str | None) -> dict | None:
    """从数据库加载模板，返回结构/风格规则 dict（兼容旧接口）。"""
    if not template_id:
        return None
    from backend.src.models.template import PromptTemplate
    t = db.get(PromptTemplate, template_id)
    if not t:
        return None
    return _parse_template_rules(t)


def _parse_template_rules(t) -> dict:
    """解析模板的 structure/style 为 dict。"""
    import json as _json
    rules = {}
    if t.structure_rules:
        try:
            rules["structure"] = _json.loads(t.structure_rules)
        except Exception:
            rules["structure"] = t.structure_rules
    if t.style_rules:
        try:
            rules["style"] = _json.loads(t.style_rules)
        except Exception:
            rules["style"] = t.style_rules
    return rules
    if not t:
        return None
    import json as _json
    rules = {}
    if t.structure_rules:
        try:
            rules["structure"] = _json.loads(t.structure_rules)
        except Exception:
            rules["structure"] = t.structure_rules
    if t.style_rules:
        try:
            rules["style"] = _json.loads(t.style_rules)
        except Exception:
            rules["style"] = t.style_rules
    return rules


def _build_context(db, session_id: int) -> str:
    """从数据库加载最近对话历史，组装为上下文字符串。

    最近 5 条消息保留完整内容，更早的消息截断到 400 字。
    """
    from backend.src.models.session import Message as Msg
    from sqlmodel import select as _sel
    msgs = db.exec(
        _sel(Msg).where(Msg.session_id == session_id)
        .order_by(Msg.created_at.desc()).limit(80)
    ).all()
    msgs = list(reversed(msgs))  # chronological order

    if not msgs:
        return ""

    recent = msgs[-30:]
    lines = ["【对话历史】"]
    full_keep = 10  # 最近 10 条保留完整内容
    for i, m in enumerate(recent):
        role = "用户" if m.role == "user" else "助手"
        is_recent = i >= len(recent) - full_keep
        if is_recent:
            txt = m.content
        else:
            txt = m.content[:400] + ("…" if len(m.content) > 400 else "")
        if txt.strip():
            lines.append(f"{role}: {txt}")

    if len(msgs) > 30:
        lines.insert(1, f"(省略了前 {len(msgs) - 30} 条消息)")

    return "\n".join(lines)


async def handle_message(
    session_id: int,
    content: str,
    command: str | None,
    profile_data: dict,
    jd_analysis: dict | None = None,
    template_id: str | None = None,
    db=None,
    session_mode: str = "normal",
) -> AsyncIterator[StreamChunk]:
    """根据 command 路由到对应的生成器，yield 结构化 chunk。

    session_mode:
      - "normal": 普通对话，不走提示词模板，仅简单问答
      - "interview": 面试模式，自动分类意图，注入完整知识库
    """

    # Load template rules — prefer per-scope default, fall back to session template_id
    template_rules = None
    if db:
        # Determine scope from effective command
        effective = command or classify_interview_intent(content)
        scope = {"intro": "self_intro", "scenario": "scenario", "technical": "technical"}.get(
            (effective or "").replace("/", ""), None)
        if scope:
            template_rules = _load_template_for_scope(db, scope)
        if not template_rules:
            template_rules = _load_template(db, template_id)

    # Build conversation context from session history
    context = _build_context(db, session_id) if db else ""

    # ── Normal mode: simple neutral chat ──
    if session_mode == "normal":
        is_interview_rel, model = classify_message(f"{command or ''} {content}")
        yield {"type": "meta", "model": model, "fast_mode": not is_interview_rel}  # type: ignore[misc]

        if is_interview_rel:
            # Auto-upgrade: if content is interview-related, use full context anyway
            sys_msg = "你是资深面试教练。基于用户简历、岗位信息和对话历史，帮用户打磨面试回答。"
            user_msg = _build_free_text_context(profile_data, jd_analysis, content, context)
        else:
            sys_msg = "你是一个有用的AI助手。回答简洁直接。"
            user_msg = content
            if context:
                user_msg = f"【对话历史】\n{context}\n\n【当前问题】\n{content}"

        async for chunk in _native_thinking_stream([
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_msg},
        ], temperature=0.5, model=model):
            yield chunk
        return

    # ── Interview mode: auto-classify → full interview pipeline ──
    is_interview, model = True, llm_client.model
    yield {"type": "meta", "model": model, "fast_mode": False}  # type: ignore[misc]

    # Auto-classify intent if no explicit command
    explicit_command = bool(command)  # True = user typed /xxx, False = auto-classified
    effective_command = command or classify_interview_intent(content)

    if effective_command == "/intro":
        extra = content.replace("/intro", "").strip() if explicit_command else content.strip()
        messages = build_intro_messages(profile_data, jd_analysis, extra, template_rules)
        if context:
            messages.insert(-1, {"role": "system", "content": f"这是本次面试准备对话的历史记录，请参考已讨论过的内容避免重复：\n{context}"})
        async for chunk in _native_thinking_stream(messages, temperature=0.4, model=model):
            yield chunk

    elif effective_command == "/scenario":
        question = content.replace("/scenario", "").strip() if explicit_command else content.strip()
        messages = build_scenario_messages(profile_data, question, jd_analysis, template_rules)
        if context:
            messages.insert(-1, {"role": "system", "content": f"对话历史（参考已讨论经历，避免重复使用相同案例）：\n{context}"})
        async for chunk in _native_thinking_stream(messages, temperature=0.4, model=model):
            yield chunk

    elif effective_command == "/followup":
        base = "你是一个有经验的面试官。"
        profile_summary = _build_profile_summary(profile_data, jd_analysis)
        if context:
            base += f"\n【用户背景】{profile_summary}\n基于以下对话历史，提出一个自然的追问。\n{context}"
        else:
            base += f"\n【用户背景】{profile_summary}\n基于以上面试准备对话，生成一个面试官可能追问的、有挑战性的问题。"
        if template_rules:
            if template_rules.get("structure"):
                base += f"\n用户指定的结构规则：{template_rules['structure']}"
            if template_rules.get("style"):
                base += f"\n用户指定的风格规则：{template_rules['style']}"
        async for chunk in _native_thinking_stream([
            {"role": "system", "content": base},
            {"role": "user", "content": "只输出追问问题本身，不加前缀。"},
        ], temperature=0.6, model=model):
            yield chunk

    elif effective_command == "/technical":
        question = content.replace("/technical", "").strip() if explicit_command else content.strip()
        messages = build_technical_messages(profile_data, question, jd_analysis, template_rules)
        if context:
            messages.insert(-1, {"role": "system", "content": f"对话历史（参考已讨论过的技术点，避免重复）：\n{context}"})
        async for chunk in _native_thinking_stream(messages, temperature=0.4, model=model):
            yield chunk

    else:
        # No clear intent → general interview coaching with full context
        sys_msg = "你是资深面试教练。基于用户提供的简历、岗位信息和知识库，回答用户关于面试、技术、职业发展等方面的问题。回答要具体、有针对性，引用用户的真实经历和技能。"
        user_msg = _build_free_text_context(profile_data, jd_analysis, content, context)
        if template_rules:
            if template_rules.get("structure"):
                sys_msg += f"\n结构规则：{template_rules['structure']}"
            if template_rules.get("style"):
                sys_msg += f"\n风格规则：{template_rules['style']}"
        async for chunk in _native_thinking_stream([
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_msg},
        ], temperature=0.5, model=model):
            yield chunk


def build_profile_data_for_prompt(db: Session) -> dict:
    """从数据库组装 profile_data + 附加文档文本用于 Prompt 注入。"""
    import json as _json
    from backend.src.models.document import SourceDocument
    from sqlmodel import select as _sel

    profile = profile_service.get_or_create_profile(db)
    internships = profile_service.list_internships(db, profile.id)
    projects = profile_service.list_projects(db, profile.id)
    skills_list = profile_service.list_skills(db, profile.id)

    # Load attached documents (usage="attach") for both scopes
    profile_docs = db.exec(
        _sel(SourceDocument)
        .where(SourceDocument.profile_id == profile.id)
        .where(SourceDocument.scope == "profile")
        .where(SourceDocument.usage == "attach")
        .where(SourceDocument.extracted_text.isnot(None))  # type: ignore[arg-type]
    ).all()
    jd_docs = db.exec(
        _sel(SourceDocument)
        .where(SourceDocument.profile_id == profile.id)
        .where(SourceDocument.scope == "jd")
        .where(SourceDocument.usage == "attach")
        .where(SourceDocument.extracted_text.isnot(None))  # type: ignore[arg-type]
    ).all()

    return {
        "name": profile.name,
        "internships": [
            {"company": i.company, "position": i.position, "achievements": _json.loads(i.achievements or "[]")}
            for i in internships
        ],
        "projects": [
                {"name": p.name, "role": p.role, "tech_stack": _json.loads(p.tech_stack or "[]"),
                 "challenge": p.challenge, "solution": p.solution, "result": p.result}
                for p in projects
            ],
            "skills": [{"category": sk.category, "name": sk.name, "proficiency": sk.proficiency} for sk in skills_list],
            "profile_docs": [{"filename": d.filename, "text": d.extracted_text[:3000]} for d in profile_docs if d.extracted_text],
            "jd_docs": [{"filename": d.filename, "text": d.extracted_text[:3000]} for d in jd_docs if d.extracted_text],
        }


def _build_profile_summary(profile_data: dict, jd_analysis: dict | None) -> str:
    """构建用户背景摘要，用于 /followup 等命令的 system prompt。"""
    parts = [f"姓名：{profile_data.get('name','')}"]

    skills = profile_data.get("skills", [])
    if skills:
        skill_names = [f"{s['name']}({s['proficiency']})" for s in skills[:8]]
        parts.append(f"技能：{', '.join(skill_names)}")

    projects = profile_data.get("projects", [])
    if projects:
        proj_names = [p["name"] for p in projects[:5]]
        parts.append(f"项目经历：{', '.join(proj_names)}")

    internships = profile_data.get("internships", [])
    if internships:
        intern_info = [f"{i['company']}-{i['position']}" for i in internships[:3]]
        parts.append(f"实习经历：{', '.join(intern_info)}")

    if jd_analysis:
        jd_parts = []
        if jd_analysis.get("core_skills"):
            jd_parts.append(f"岗位技能要求：{', '.join(jd_analysis['core_skills'][:5])}")
        if jd_analysis.get("duties"):
            jd_parts.append(f"岗位职责：{', '.join(jd_analysis['duties'][:3])}")
        if jd_parts:
            parts.append("；".join(jd_parts))

    return "\n".join(parts)


def _build_free_text_context(profile_data: dict, jd_analysis: dict | None, content: str, context: str) -> str:
    """为自由对话构建包含完整知识库上下文的 user message。"""
    import json as _json

    sections = []

    # Structured profile
    profile_parts = [f"姓名：{profile_data.get('name','')}"]
    for exp in profile_data.get("internships", []):
        ach = exp.get("achievements", [])
        profile_parts.append(f"实习：{exp['company']} {exp['position']} · 成果：{'；'.join(ach[:3])}")
    for proj in profile_data.get("projects", []):
        profile_parts.append(f"项目：{proj['name']}（角色：{proj['role']}）· 挑战：{proj['challenge']} · 方案：{proj['solution']} · 结果：{proj['result']}")
    skills_by_cat = {}
    for s in profile_data.get("skills", []):
        skills_by_cat.setdefault(s["category"], []).append(f"{s['name']}({s['proficiency']})")
    for cat, items in skills_by_cat.items():
        profile_parts.append(f"技能-{cat}：{', '.join(items)}")
    sections.append("【用户简历】\n" + "\n".join(profile_parts))

    # JD analysis
    if jd_analysis:
        jd_parts = []
        if jd_analysis.get("core_skills"):
            jd_parts.append(f"核心技能要求：{', '.join(jd_analysis['core_skills'])}")
        if jd_analysis.get("duties"):
            jd_parts.append(f"主要职责：{', '.join(jd_analysis['duties'])}")
        if jd_analysis.get("culture_values"):
            jd_parts.append(f"公司价值观/方向：{', '.join(jd_analysis['culture_values'])}")
        if jd_parts:
            sections.append("【目标岗位信息】\n" + "；".join(jd_parts))
    else:
        sections.append("【目标岗位信息】\n通用面试模式（未提供岗位信息）")

    # Attached documents
    for doc in profile_data.get("profile_docs", []):
        sections.append(f"【附加个人素材-{doc['filename']}】\n{doc['text']}")
    for doc in profile_data.get("jd_docs", []):
        sections.append(f"【附加公司素材-{doc['filename']}】\n{doc['text']}")

    # Conversation history
    if context:
        sections.append(f"【对话历史】\n{context}")

    # Current question
    sections.append(f"【当前问题】\n{content}")

    return "\n\n".join(sections)
