"""生成 API 路由 —— SSE 流式端点"""

import json
from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse
from sqlmodel import Session

from backend.src.db.connection import engine, get_session
from backend.src.services import profile_service, session_service, conversation_service
from backend.src.api.settings import LLM_PROVIDERS
from backend.src.services.context_builder import ContextBuilder
from backend.src.services.generation_guard import (
    generation_guard,
    public_generation_error,
    validate_owned_session,
)
from backend.src.services.memory_service import refresh_conversation_summary

router = APIRouter(prefix="/api", tags=["generate"])

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

    if not isinstance(session_id, int) or session_id <= 0:
        return EventSourceResponse(_error("缺少 session_id"))

    profile = profile_service.get_active_profile(session)
    try:
        conv_sess = validate_owned_session(session, session_id, profile.id)
    except Exception as exc:
        return EventSourceResponse(_error(public_generation_error(exc)))

    guard_key = f"session:{session_id}"
    guard_error = generation_guard.try_acquire(guard_key)
    if guard_error:
        return EventSourceResponse(_error(guard_error))

    try:
        # Reconfigure LLM from user settings (API key / provider / model from DB)
        _apply_llm_settings(session)
        builder = ContextBuilder(session)
        profile_data = builder.load_profile_data(profile.id)
        session_mode = conv_sess.mode
        jd_analysis = builder.load_active_jd(profile.id)

        # Add user message only after ownership and guard checks pass.
        user_message = session_service.add_message(
            session, session_id, role="user", content=content,
            msg_type=_type_from_command(command), command=command
        )
        # ORM objects become detached when FastAPI closes the request dependency
        # before consuming the SSE body. Keep only the scalar value in the stream.
        user_message_id = user_message.id
    except Exception as exc:
        generation_guard.release(guard_key)
        import logging
        logging.getLogger("speakwise").error("生成准备失败: %s", exc, exc_info=True)
        return EventSourceResponse(_error(public_generation_error(exc)))

    # Collect assistant response + thinking
    full_response = ""
    full_thinking = ""

    async def _stream(stream_session: Session):
        nonlocal full_response, full_thinking

        effective_intent = command
        if session_mode == "interview" and not effective_intent:
            effective_intent = await conversation_service.classify_interview_intent_hybrid(
                content,
                db=stream_session,
                session_id=session_id,
                current_message_id=user_message_id,
            )

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
                intent_label = {
                    "intro": "自我介绍", "scenario": "场景题",
                    "technical": "技术题", "followup": "模拟追问",
                }.get((effective_intent or "").replace("/", ""), "通用问答")
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
            tpl_name = (effective_intent or "通用").replace("/", "")
            system_lines.append(f"使用 {model} 模型和 {tpl_name} 提示词模板")
        else:
            is_interview, model = conversation_service.classify_message(f"{command or ''} {content}")
            system_lines.append(f"使用 {model} 模型")

        # Emit as one flowing paragraph
        yield {"event": "thinking", "data": "。".join(system_lines) + "。\n\n"}

        # ── Phase 2: LLM streaming ──
        first_chunk = True
        try:
            await refresh_conversation_summary(
                stream_session, session_id, exclude_message_id=user_message_id
            )
            async for chunk in conversation_service.handle_message(
                session_id=session_id, content=content, command=command,
                profile_data=profile_data, jd_analysis=jd_analysis,
                template_id=template_id, db=stream_session, session_mode=session_mode,
                current_message_id=user_message_id,
                resolved_intent=effective_intent, intent_is_resolved=True,
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
            yield {"event": "error", "data": public_generation_error(e)}
            return

        # Save assistant message (with thinking if any)
        session_service.add_message(
            stream_session, session_id, role="assistant", content=full_response,
            msg_type=_type_from_command(effective_intent), command=effective_intent,
            thinking=full_thinking or None,
        )

        # Done event with metrics
        yield {"event": "done", "data": json.dumps({
            "content": full_response,
            "length": len(full_response),
        }, ensure_ascii=False)}

    async def _wrapped_stream():
        try:
            # A request dependency may be closed before StreamingResponse finishes.
            # Own the DB session for exactly the lifetime of the SSE iteration.
            with Session(engine) as stream_session:
                async for event in _stream(stream_session):
                    yield event
        finally:
            generation_guard.release(guard_key)

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
