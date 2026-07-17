"""模拟面试 API — SSE 流式端点"""

import json
from fastapi import APIRouter, Depends, Request, Body
from sse_starlette.sse import EventSourceResponse
from sqlmodel import Session

from backend.src.db.connection import get_session
from backend.src.services import profile_service, session_service, conversation_service
from backend.src.llm.client import llm_client
from backend.src.models.job_context import JobContext
from backend.src.prompts import interview as interview_prompts
from backend.src.models.session import Message

router = APIRouter(prefix="/api/interview", tags=["interview"])


def _get_knowledge(session: Session) -> tuple[dict, dict | None]:
    profile = profile_service.get_active_profile(session)
    profile_data = conversation_service.build_profile_data_for_prompt(session, profile.id)
    jd = session.exec(
        __import__("sqlmodel").select(JobContext)
        .where(JobContext.profile_id == profile.id)
        .where(JobContext.is_active == True)  # noqa: E712
    ).first()
    return profile_data, jd.to_analysis_dict() if jd else None


def _apply_llm(db):
    from backend.src.api.settings import get_active_apikey, LLM_PROVIDERS
    active = get_active_apikey(db)
    if active and active["api_key"]:
        p = LLM_PROVIDERS.get(active["provider"])
        llm_client.configure(api_key=active["api_key"], base_url=p["base_url"] if p else None, model=active.get("model") or None)
    else:
        llm_client.configure(api_key="", base_url=None, model=None)


async def _stream_llm(messages: list[dict], temperature: float = 0.4):
    full = ""
    thinking = ""
    async for chunk in llm_client.stream(messages, temperature=temperature):
        t = chunk.get("type", "token")
        text = chunk.get("content", "")
        if t == "thinking":
            thinking += text
            yield {"event": "thinking", "data": text}
        else:
            full += text
            yield {"event": "token", "data": text}
    yield {"event": "done", "data": json.dumps({"content": full, "length": len(full)}, ensure_ascii=False)}


@router.post("/start")
async def interview_start(request: Request, session: Session = Depends(get_session)):
    """开始模拟面试：创建会话 → 流式输出第一题。"""
    _apply_llm(session)
    profile = profile_service.get_active_profile(session)
    profile_data, jd = _get_knowledge(session)

    # Create mock interview session
    conv = session_service.create_session(session, profile.id, "模拟面试", mode="mock")

    messages = interview_prompts.build_start_prompt(profile_data, jd)

    question_content = ""
    thinking_content = ""

    async def _stream():
        nonlocal question_content, thinking_content
        async for chunk in llm_client.stream(messages, temperature=0.6):
            t = chunk.get("type", "token")
            text = chunk.get("content", "")
            if t == "thinking":
                thinking_content += text
                yield {"event": "thinking", "data": text}
            else:
                question_content += text
                yield {"event": "token", "data": text}

        # Save question as message
        if question_content.strip():
            session_service.add_message(
                session, conv.id, role="assistant", content=question_content,
                msg_type="interview_question", thinking=thinking_content or None,
            )

        yield {"event": "done", "data": json.dumps({
            "content": question_content,
            "session_id": conv.id,
            "length": len(question_content),
        }, ensure_ascii=False)}

    return EventSourceResponse(_stream())


@router.post("/respond")
async def interview_respond(request: Request, session: Session = Depends(get_session)):
    """处理用户回应。body: { session_id, action, answer? }
    action: "answer" | "reference" | "skip"
    """
    body = await request.json()
    session_id = body.get("session_id")
    action = body.get("action", "answer")
    user_answer = body.get("answer", "").strip()

    if not session_id:
        return EventSourceResponse(_error("缺少 session_id"))

    _apply_llm(session)
    profile_data, jd = _get_knowledge(session)

    # Get the last question from messages
    last_question = _get_last_question(session, session_id)
    if not last_question:
        return EventSourceResponse(_error("未找到当前问题"))

    recent = conversation_service._get_recent_messages(session, session_id)

    # ── Route by action ──
    if action == "skip":
        # Ignore current question, generate replacement
        messages = interview_prompts.build_replace_prompt(profile_data, jd, last_question, recent)
    elif action == "reference":
        # Generate reference answer only, then next question
        messages = interview_prompts.build_reference_prompt(profile_data, jd, last_question, recent)
    else:
        # "answer": evaluate + reference + next question
        if not user_answer:
            return EventSourceResponse(_error("回答不能为空"))
        messages = interview_prompts.build_evaluate_prompt(profile_data, jd, last_question, user_answer, recent)

    response_content = ""
    thinking_content = ""

    async def _stream():
        nonlocal response_content, thinking_content

        # Save user answer first (if answering)
        if action == "answer" and user_answer:
            session_service.add_message(session, session_id, role="user", content=user_answer, msg_type="free_text")

        async for chunk in llm_client.stream(messages, temperature=0.5):
            t = chunk.get("type", "token")
            text = chunk.get("content", "")
            if t == "thinking":
                thinking_content += text
                yield {"event": "thinking", "data": text}
            else:
                response_content += text
                yield {"event": "token", "data": text}

        # Save response as message
        if response_content.strip():
            msg_type = "interview_eval" if action == "answer" else "interview_reference" if action == "reference" else "interview_question"
            session_service.add_message(
                session, session_id, role="assistant", content=response_content,
                msg_type=msg_type, thinking=thinking_content or None,
            )

        yield {"event": "done", "data": json.dumps({
            "content": response_content,
            "session_id": session_id,
            "length": len(response_content),
        }, ensure_ascii=False)}

    return EventSourceResponse(_stream())


@router.post("/next")
async def interview_next(request: Request, session: Session = Depends(get_session)):
    """生成下一个面试问题。body: { session_id }"""
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        return EventSourceResponse(_error("缺少 session_id"))

    _apply_llm(session)
    profile_data, jd = _get_knowledge(session)
    recent = conversation_service._get_recent_messages(session, session_id)

    messages = interview_prompts.build_next_question_prompt(profile_data, jd, recent)

    question_content = ""
    thinking_content = ""

    async def _stream():
        nonlocal question_content, thinking_content
        async for chunk in llm_client.stream(messages, temperature=0.6):
            t = chunk.get("type", "token")
            text = chunk.get("content", "")
            if t == "thinking":
                thinking_content += text
                yield {"event": "thinking", "data": text}
            else:
                question_content += text
                yield {"event": "token", "data": text}

        if question_content.strip():
            session_service.add_message(
                session, session_id, role="assistant", content=question_content,
                msg_type="interview_question", thinking=thinking_content or None,
            )

        yield {"event": "done", "data": json.dumps({
            "content": question_content,
            "session_id": session_id,
            "length": len(question_content),
        }, ensure_ascii=False)}

    return EventSourceResponse(_stream())


@router.post("/summary")
async def interview_summary(request: Request, session: Session = Depends(get_session)):
    """生成面试汇总文档。body: { session_id }"""
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        return EventSourceResponse(_error("缺少 session_id"))

    _apply_llm(session)

    # Collect all QA records from messages
    all_msgs = session_service.list_messages(session, session_id)
    qa_list = _extract_qa(all_msgs)

    messages = interview_prompts.build_summary_prompt(qa_list)
    summary_content = ""

    async def _stream():
        nonlocal summary_content
        async for chunk in llm_client.stream(messages, temperature=0.3):
            t = chunk.get("type", "token")
            text = chunk.get("content", "")
            if t == "token":
                summary_content += text
                yield {"event": "token", "data": text}

        if summary_content.strip():
            session_service.add_message(
                session, session_id, role="assistant", content=summary_content,
                msg_type="interview_summary",
            )

        yield {"event": "done", "data": json.dumps({
            "content": summary_content,
            "length": len(summary_content),
        }, ensure_ascii=False)}

    return EventSourceResponse(_stream())


# ── Helpers ──

def _get_last_question(db, session_id: int) -> str | None:
    from sqlmodel import select as _sel
    msg = db.exec(
        _sel(Message)
        .where(Message.session_id == session_id)
        .where(Message.type.in_(["interview_question"]))  # type: ignore[arg-type]
        .order_by(Message.created_at.desc())
    ).first()
    return msg.content if msg else None


def _extract_qa(all_msgs: list[Message]) -> list[dict]:
    """从消息列表提取有效 QA 对（跳过被忽略的题）。"""
    qa_list = []
    current_q = None
    for m in all_msgs:
        if m.type == "interview_question":
            # Save previous question only if it has content beyond just the question
            if current_q:
                has_response = current_q.get("user_answer") or current_q.get("evaluation") or current_q.get("reference_answer")
                if has_response:
                    # Determine type
                    if current_q.get("user_answer"):
                        current_q["qa_type"] = "answered"
                    else:
                        current_q["qa_type"] = "reference_only"
                    qa_list.append(current_q)
                # else: skipped question — discard
            current_q = {"question": m.content}
        elif m.role == "user" and current_q:
            current_q["user_answer"] = m.content
        elif m.type == "interview_eval" and current_q:
            current_q["evaluation"] = m.content
        elif m.type == "interview_reference" and current_q:
            current_q["reference_answer"] = m.content
    # Last question
    if current_q:
        has_response = current_q.get("user_answer") or current_q.get("evaluation") or current_q.get("reference_answer")
        if has_response:
            if current_q.get("user_answer"):
                current_q["qa_type"] = "answered"
            else:
                current_q["qa_type"] = "reference_only"
            qa_list.append(current_q)
    return qa_list


async def _error(msg: str):
    yield {"event": "error", "data": msg}
