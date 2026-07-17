"""生成 API 路由 —— SSE 流式端点"""

import json
from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse
from sqlmodel import Session

from backend.src.db.connection import get_session
from backend.src.services import profile_service, session_service, conversation_service
from backend.src.llm.client import llm_client
from backend.src.models.job_context import JobContext
from backend.src.api.settings import LLM_PROVIDERS

router = APIRouter(prefix="/api", tags=["generate"])

import time

# Session-level concurrency lock: prevent duplicate LLM calls for the same session
_active_generations: dict[int, bool] = {}
# Rate limiter: max 10 requests per 30 seconds per session
_rate_limit: dict[int, list[float]] = {}
_RATE_LIMIT_MAX = 10
_RATE_LIMIT_WINDOW = 30.0


@router.post("/generate")
async def generate(request: Request, session: Session = Depends(get_session)):
    """统一的生成入口。根据消息中的 command 字段路由。

    Request body: { session_id, content, command? }
    SSE events: meta → token* → done
    """
    body = await request.json()
    session_id = body.get("session_id")
    content = body.get("content", "")
    command = body.get("command")
    template_id = body.get("template_id")

    if not session_id:
        return EventSourceResponse(_error("缺少 session_id"))

    # Rate limit check
    now = time.time()
    window = _rate_limit.get(session_id, [])
    window = [t for t in window if now - t < _RATE_LIMIT_WINDOW]
    if len(window) >= _RATE_LIMIT_MAX:
        return EventSourceResponse(_error("请求过于频繁，请稍后再试"))
    window.append(now)
    _rate_limit[session_id] = window

    # Concurrency check: only one generation per session at a time
    if _active_generations.get(session_id):
        return EventSourceResponse(_error("上一个请求尚未完成，请稍后"))

    _active_generations[session_id] = True

    # Reconfigure LLM from user settings (API key / provider / model from DB)
    _apply_llm_settings(session)

    # Profile data + session mode (use active profile only)
    profile = profile_service.get_active_profile(session)
    profile_data = conversation_service.build_profile_data_for_prompt(session, profile.id if profile else 1)
    conv_sess = session_service.get_session(session, session_id)
    session_mode = conv_sess.mode if conv_sess else "normal"

    # Load active JD context (is_active=True, not just latest)
    jd_analysis = None
    jc = session.exec(
        __import__("sqlmodel").select(JobContext)
        .where(JobContext.profile_id == profile.id)
        .where(JobContext.is_active == True)  # noqa: E712
        .order_by(JobContext.id.desc())
    ).first()
    if jc:
        jd_analysis = jc.to_analysis_dict()

    # Add user message to session
    session_service.add_message(
        session, session_id, role="user", content=content,
        msg_type=_type_from_command(command), command=command
    )

    # Collect assistant response + thinking
    full_response = ""
    full_thinking = ""

    async def _stream():
        nonlocal full_response, full_thinking

        # ── Phase 1: System context summary (one flowing narrative) ──
        yield {"event": "meta", "data": json.dumps({
            "command": command, "session_id": session_id,
            "session_mode": session_mode,
        }, ensure_ascii=False)}

        # Build a single cohesive system analysis that flows into LLM reasoning
        system_lines = []

        # Mode + Intent
        if session_mode == "interview":
            if command:
                system_lines.append(f"当前为面试对话模式，用户使用了显式命令 {command}")
            else:
                intent = conversation_service.classify_interview_intent(content)
                intent_label = {"intro": "自我介绍", "scenario": "场景题", "technical": "技术题"}.get(
                    (intent or "").replace("/", ""), "通用问答")
                system_lines.append(f"当前为面试对话模式，我识别到用户意图为「{intent_label}」")
        else:
            is_rel, _ = conversation_service.classify_message(content)
            system_lines.append(f"当前为普通对话模式，用户问题{'涉及面试话题' if is_rel else '为通用问题'}")

        # Knowledge base summary
        skills_n = len(profile_data.get("skills", []))
        projects_n = len(profile_data.get("projects", []))
        internships_n = len(profile_data.get("internships", []))
        kb_desc = f"已加载用户知识库（{skills_n}项技能、{projects_n}个项目"
        if internships_n:
            kb_desc += f"、{internships_n}段实习"
        kb_desc += "）"
        system_lines.append(kb_desc)

        # JD
        if jd_analysis and jd_analysis.get("core_skills"):
            system_lines.append(f"目标岗位要求 {len(jd_analysis.get('core_skills',[]))} 项核心技能")
        else:
            system_lines.append("未提供岗位JD信息")

        # Documents
        profile_docs = profile_data.get("profile_docs", [])
        jd_docs = profile_data.get("jd_docs", [])
        if profile_docs or jd_docs:
            doc_parts = []
            if profile_docs:
                doc_parts.append(f"{len(profile_docs)}份个人素材")
            if jd_docs:
                doc_parts.append(f"{len(jd_docs)}份公司素材")
            system_lines.append(f"附带参考文档：{'、'.join(doc_parts)}")

        # Model + Template
        if session_mode == "interview":
            model = conversation_service.llm_client.model
            tpl_name = (command or conversation_service.classify_interview_intent(content) or "通用").replace("/", "")
            system_lines.append(f"使用 {model} 模型和 {tpl_name} 提示词模板")
        else:
            is_interview, model = conversation_service.classify_message(f"{command or ''} {content}")
            system_lines.append(f"使用 {model} 模型")

        # Emit as one flowing paragraph
        yield {"event": "thinking", "data": "。".join(system_lines) + "。\n\n"}

        # ── Phase 2: LLM streaming ──
        first_chunk = True
        try:
            async for chunk in conversation_service.handle_message(
                session_id=session_id, content=content, command=command,
                profile_data=profile_data, jd_analysis=jd_analysis,
                template_id=template_id, db=session, session_mode=session_mode,
            ):
                chunk_type = chunk.get("type", "token")
                text = chunk.get("content", "")

                # Skip the internal meta chunk from handle_message
                if first_chunk and chunk_type == "meta":
                    first_chunk = False
                    continue

                first_chunk = False
                if chunk_type == "thinking":
                    full_thinking += text
                    yield {"event": "thinking", "data": text}
                else:
                    full_response += text
                    yield {"event": "token", "data": text}
        except Exception as e:
            import logging
            logging.getLogger("speakwise").error("生成失败: %s", e, exc_info=True)
            yield {"event": "error", "data": "生成失败，请重试"}
            return

        # Save assistant message (with thinking if any)
        session_service.add_message(
            session, session_id, role="assistant", content=full_response,
            msg_type=_type_from_command(command), command=command,
            thinking=full_thinking or None,
        )

        # Done event with metrics
        yield {"event": "done", "data": json.dumps({
            "content": full_response,
            "length": len(full_response),
        }, ensure_ascii=False)}

    async def _wrapped_stream():
        try:
            async for event in _stream():
                yield event
        finally:
            _active_generations.pop(session_id, None)

    return EventSourceResponse(_wrapped_stream())


def _type_from_command(cmd: str | None) -> str:
    if cmd == "/intro": return "self_intro"
    if cmd == "/scenario": return "scenario"
    if cmd == "/technical": return "technical"
    if cmd == "/followup": return "follow_up"
    return "free_text"


async def _error(msg: str):
    yield {"event": "error", "data": msg}


def _apply_llm_settings(db):
    """从数据库加载活跃 API Key + LLM 模型配置到全局 LLM 客户端。"""
    from backend.src.api.settings import get_active_apikey
    active = get_active_apikey(db)
    if active and active["api_key"]:
        provider = LLM_PROVIDERS.get(active["provider"])
        base_url = provider["base_url"] if provider else None
        conversation_service.llm_client.configure(
            api_key=active["api_key"],
            base_url=base_url,
            model=active.get("model") or None,
        )
    else:
        # No active key — reset client to prevent stale config
        conversation_service.llm_client.configure(
            api_key="", base_url=None, model=None,
        )
