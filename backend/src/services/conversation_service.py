"""对话服务：斜杠命令路由 + 上下文组装 + 生成编排"""

import json
import logging
from typing import AsyncIterator

from sqlmodel import Session, select
from backend.src.llm.client import llm_client, StreamChunk
from backend.src.models.session import Message
from backend.src.prompts.self_intro import build_intro_messages
from backend.src.prompts.scenario import build_scenario_messages
from backend.src.prompts.technical import build_technical_messages
from backend.src.services import profile_service
from backend.src.services.context_builder import ContextBuilder


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
    return False, llm_client.fast_model()


# ── 面试模式下的意图分类 ────────────────────────────────────

_INTENT_WEIGHTS = {
    "/intro": {
        "自我介绍": 4, "介绍自己": 4, "个人介绍": 4,
        "self intro": 4, "introduce yourself": 4,
        "我叫": 3, "我的经历": 2, "概述自己": 3,
    },
    "/technical": {
        "算法": 3, "数据结构": 3, "代码": 2, "编程": 2,
        "leetcode": 3, "系统设计": 3, "设计模式": 3,
        "时间复杂度": 3, "网络协议": 3, "操作系统": 3,
        "数据库": 3, "sql": 3, "react": 3, "vue": 3,
        "fastapi": 3, "django": 3, "flask": 3,
        "langgraph": 3, "langchain": 3, "docker": 3,
        "kubernetes": 3, "redis": 3, "mongodb": 3, "postgresql": 3,
        "手写": 2, "复杂度": 2, "底层": 2, "架构": 2,
        "实现": 1, "原理": 1, "区别": 1, "优缺点": 1,
        "coding": 3, "system design": 3,
    },
    "/scenario": {
        "场景题": 4, "行为面试": 4, "behavioral": 4, "star": 4,
        "怎么处理": 3, "如何解决": 3, "讲一个": 2, "举例": 2,
        "冲突": 3, "失败": 2, "挑战": 2, "团队": 1,
        "领导": 1, "沟通": 1, "项目经历": 2, "案例": 2,
    },
}

_FOLLOWUP_MARKERS = ("那", "这个", "还有", "继续", "再说", "具体", "为什么", "呢")
_VALID_LLM_INTENTS = {"intro", "scenario", "technical", "followup", "general"}


def _explicit_intent(text_lower: str) -> str | None:
    for command in ("/intro", "/scenario", "/technical", "/followup"):
        if text_lower.startswith(command):
            return command
    return None


def _intent_scores(text_lower: str) -> dict[str, int]:
    return {
        intent: sum(weight for keyword, weight in keywords.items() if keyword in text_lower)
        for intent, keywords in _INTENT_WEIGHTS.items()
    }


def classify_interview_intent(content: str) -> str | None:
    """在面试模式下自动识别用户意图，返回命令类型。

    返回: "/intro" | "/scenario" | "/technical" | None（通用问答）
    """
    text_lower = content.lower()

    explicit = _explicit_intent(text_lower)
    if explicit:
        return explicit

    scores = _intent_scores(text_lower)
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_intent, best_score = ranked[0]
    second_score = ranked[1][1]
    if best_score >= 3 and best_score - second_score >= 2:
        return best_intent

    # Low-confidence or conflicting rules are delegated to the fast model.
    return None


def _recent_interview_intent(
    db: Session | None, session_id: int | None, exclude_message_id: int | None
) -> str | None:
    if not db or not session_id:
        return None
    statement = select(Message).where(Message.session_id == session_id)
    if exclude_message_id:
        statement = statement.where(Message.id != exclude_message_id)
    recent = list(db.exec(statement.order_by(Message.id.desc()).limit(10)).all())
    type_map = {
        "self_intro": "/intro", "scenario": "/scenario",
        "technical": "/technical", "follow_up": "/followup",
    }
    for message in recent:
        if message.command in {"/intro", "/scenario", "/technical", "/followup"}:
            return message.command
        if message.type in type_map:
            return type_map[message.type]
    return None


async def classify_interview_intent_hybrid(
    content: str,
    *,
    db: Session | None = None,
    session_id: int | None = None,
    current_message_id: int | None = None,
) -> str | None:
    """Classify once per interview request: command → rules → history → fast LLM."""
    text = content.strip()
    rule_intent = classify_interview_intent(text)
    if rule_intent:
        return rule_intent

    if len(text) <= 20 and any(marker in text.lower() for marker in _FOLLOWUP_MARKERS):
        recent_intent = _recent_interview_intent(db, session_id, current_message_id)
        if recent_intent:
            return recent_intent

    prompt = f"""判断下面这句话在面试准备中的主要意图。
只返回 JSON：{{"intent":"intro|scenario|technical|followup|general","confidence":0到1}}

分类说明：
- intro：生成或修改自我介绍
- scenario：行为题、STAR、项目挑战、团队冲突
- technical：技术知识、编程、系统设计
- followup：要求面试官继续追问
- general：无法归入以上类别

用户消息：{text[:1000]}"""
    try:
        raw = await llm_client.chat(
            [{"role": "system", "content": "你是面试意图分类器。"},
             {"role": "user", "content": prompt}],
            temperature=0,
            model=llm_client.fast_model(),
        )
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
        result = json.loads(cleaned)
        intent = str(result.get("intent", "general")).lower()
        confidence = float(result.get("confidence", 0))
        if intent in _VALID_LLM_INTENTS and confidence >= 0.6:
            return None if intent == "general" else f"/{intent}"
    except Exception as exc:
        logging.getLogger("speakwise").warning("面试意图分类失败: %s", exc)
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
    profile = profile_service.get_active_profile(db)
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


async def handle_message(
    session_id: int,
    content: str,
    command: str | None,
    profile_data: dict,
    jd_analysis: dict | None = None,
    template_id: str | None = None,
    db=None,
    session_mode: str = "normal",
    current_message_id: int | None = None,
    resolved_intent: str | None = None,
    intent_is_resolved: bool = False,
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
        effective = (
            resolved_intent if intent_is_resolved
            else command or classify_interview_intent(content)
        )
        scope = {"intro": "self_intro", "scenario": "scenario", "technical": "technical"}.get(
            (effective or "").replace("/", ""), None)
        if scope:
            template_rules = _load_template_for_scope(db, scope)
        if not template_rules:
            template_rules = _load_template(db, template_id)

    history_messages = (
        ContextBuilder(db).build_history_messages(
            session_id, exclude_message_id=current_message_id
        )
        if db else []
    )

    # ── Normal mode: simple neutral chat ──
    if session_mode == "normal":
        is_interview_rel, model = classify_message(f"{command or ''} {content}")
        yield {"type": "meta", "model": model, "fast_mode": not is_interview_rel}  # type: ignore[misc]

        if is_interview_rel:
            sys_msg = "你是资深面试教练。基于用户简历、岗位信息和对话历史，帮用户打磨面试回答。"
            user_msg = _build_free_text_context(profile_data, jd_analysis, content, "")
            messages = [{"role": "system", "content": sys_msg}]
            messages += history_messages
            messages.append({"role": "user", "content": user_msg})
        else:
            sys_msg = "你是一个有用的AI助手。回答简洁直接。"
            messages = [{"role": "system", "content": sys_msg}]
            messages += history_messages
            messages.append({"role": "user", "content": content})

        async for chunk in _native_thinking_stream(messages, temperature=0.5, model=model):
            yield chunk
        return

    # ── Interview mode: auto-classify → full interview pipeline ──
    is_interview, model = True, llm_client.model
    yield {"type": "meta", "model": model, "fast_mode": False}  # type: ignore[misc]

    # Auto-classify intent if no explicit command
    explicit_command = bool(command)
    effective_command = (
        resolved_intent if intent_is_resolved
        else command or classify_interview_intent(content)
    )
    recent_msgs = history_messages

    if effective_command == "/intro":
        extra = content.replace("/intro", "").strip() if explicit_command else content.strip()
        messages = build_intro_messages(profile_data, jd_analysis, extra, template_rules)
        # Insert history as native role messages before the final user message
        if recent_msgs:
            messages = messages[:-1] + recent_msgs + [messages[-1]]
        async for chunk in _native_thinking_stream(messages, temperature=0.4, model=model):
            yield chunk

    elif effective_command == "/scenario":
        question = content.replace("/scenario", "").strip() if explicit_command else content.strip()
        messages = build_scenario_messages(profile_data, question, jd_analysis, template_rules)
        if recent_msgs:
            messages = messages[:-1] + recent_msgs + [messages[-1]]
        async for chunk in _native_thinking_stream(messages, temperature=0.4, model=model):
            yield chunk

    elif effective_command == "/followup":
        base = "你是一个有经验的面试官。"
        profile_summary = _build_profile_summary(profile_data, jd_analysis)
        base += f"\n【用户背景】{profile_summary}"
        if recent_msgs:
            base += "\n基于以上对话历史，提出一个自然的追问。"
        else:
            base += "\n基于以上面试准备对话，生成一个面试官可能追问的、有挑战性的问题。"
        user_extra = "只输出追问问题本身，不加前缀。"
        if template_rules:
            if template_rules.get("structure"):
                user_extra += f"\n用户指定的结构规则：{template_rules['structure']}"
            if template_rules.get("style"):
                user_extra += f"\n用户指定的风格规则：{template_rules['style']}"
        followup_msgs = [{"role": "system", "content": base}]
        if recent_msgs:
            followup_msgs += recent_msgs
        followup_msgs.append({"role": "user", "content": user_extra})
        async for chunk in _native_thinking_stream(followup_msgs, temperature=0.6, model=model):
            yield chunk

    elif effective_command == "/technical":
        question = content.replace("/technical", "").strip() if explicit_command else content.strip()
        messages = build_technical_messages(profile_data, question, jd_analysis, template_rules)
        if recent_msgs:
            messages = messages[:-1] + recent_msgs + [messages[-1]]
        async for chunk in _native_thinking_stream(messages, temperature=0.4, model=model):
            yield chunk

    else:
        # No clear intent → general interview coaching with full context
        sys_msg = "你是资深面试教练。基于用户提供的简历、岗位信息和知识库，回答用户关于面试、技术、职业发展等方面的问题。回答要具体、有针对性，引用用户的真实经历和技能。如果你之前已经回答过类似的问题，请在之前回答的基础上优化调整，无需从零重新生成。"
        user_msg = _build_free_text_context(profile_data, jd_analysis, content, "")
        if template_rules:
            if template_rules.get("structure"):
                user_msg += f"\n用户指定的结构规则：{template_rules['structure']}"
            if template_rules.get("style"):
                user_msg += f"\n用户指定的风格规则：{template_rules['style']}"
        messages = [{"role": "system", "content": sys_msg}]
        if recent_msgs:
            messages += recent_msgs
        messages.append({"role": "user", "content": user_msg})
        async for chunk in _native_thinking_stream(messages, temperature=0.5, model=model):
            yield chunk


def build_profile_data_for_prompt(db: Session, profile_id: int = 1) -> dict:
    """兼容入口：统一委托给 ContextBuilder。"""
    return ContextBuilder(db).load_profile_data(profile_id)


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
    """统一构建知识上下文；历史仅作为原生 messages 注入，避免重复。"""
    return ContextBuilder(None).build_knowledge_context(
        profile_data, jd_analysis, content
    )
