"""模拟面试 API — SSE 流式端点"""

import json
import logging
from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse
from sqlmodel import Session

from backend.src.db.connection import get_session
from backend.src.services import profile_service, session_service
from backend.src.llm.client import llm_client
from backend.src.prompts import interview as interview_prompts
from backend.src.models.session import Message
from backend.src.services.context_builder import ContextBuilder
from backend.src.services.generation_guard import (
    generation_guard,
    public_generation_error,
    validate_owned_session,
)
from backend.src.services.memory_service import refresh_conversation_summary

router = APIRouter(prefix="/api/interview", tags=["interview"])


def _get_knowledge(session: Session) -> tuple[dict, dict | None]:
    profile = profile_service.get_active_profile(session)
    builder = ContextBuilder(session)
    return builder.load_profile_data(profile.id), builder.load_active_jd(profile.id)


def _apply_llm(db):
    from backend.src.api.settings import get_active_apikey, LLM_PROVIDERS
    active = get_active_apikey(db)
    if active and active["api_key"]:
        p = LLM_PROVIDERS.get(active["provider"])
        llm_client.configure(api_key=active["api_key"], base_url=p["base_url"] if p else None, model=active.get("model") or None)
    else:
        llm_client.configure(api_key="", base_url=None, model=None)


@router.post("/start")
async def interview_start(request: Request, session: Session = Depends(get_session)):
    """开始模拟面试：创建会话 → 流式输出第一题。"""
    profile = profile_service.get_active_profile(session)
    guard_key = f"profile:{profile.id}:interview:start"
    guard_error = generation_guard.try_acquire(guard_key)
    if guard_error:
        return EventSourceResponse(_error(guard_error))
    try:
        _apply_llm(session)
        profile_data, jd = _get_knowledge(session)
        conv = session_service.create_session(session, profile.id, "模拟面试", mode="mock")
        messages = interview_prompts.build_start_prompt(profile_data, jd)
    except Exception as exc:
        generation_guard.release(guard_key)
        logging.getLogger("speakwise").error("模拟面试启动准备失败: %s", exc, exc_info=True)
        return EventSourceResponse(_error(public_generation_error(exc)))

    question_content = ""
    thinking_content = ""

    async def _stream():
        nonlocal question_content, thinking_content
        try:
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
                    session, conv.id, role="assistant", content=question_content,
                    msg_type="interview_question", thinking=thinking_content or None,
                )
            yield {"event": "done", "data": json.dumps({
                "content": question_content,
                "session_id": conv.id,
                "length": len(question_content),
            }, ensure_ascii=False)}
        except Exception as exc:
            logging.getLogger("speakwise").error("模拟面试启动失败: %s", exc, exc_info=True)
            yield {"event": "error", "data": public_generation_error(exc)}
        finally:
            generation_guard.release(guard_key)

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
    if action not in {"answer", "reference", "skip"}:
        return EventSourceResponse(_error("不支持的回应动作"))

    profile = profile_service.get_active_profile(session)
    try:
        validate_owned_session(session, session_id, profile.id, required_mode="mock")
    except Exception as exc:
        return EventSourceResponse(_error(public_generation_error(exc)))
    guard_key = f"session:{session_id}"
    guard_error = generation_guard.try_acquire(guard_key)
    if guard_error:
        return EventSourceResponse(_error(guard_error))

    try:
        _apply_llm(session)
        profile_data, jd = _get_knowledge(session)
        last_question_message = _get_last_question_message(session, session_id)
        if not last_question_message:
            raise ValueError("未找到当前问题")
        last_question = last_question_message.content
        await refresh_conversation_summary(session, session_id)
        recent = ContextBuilder(session).build_history_messages(
            session_id, exclude_message_id=last_question_message.id
        )
        if action == "skip":
            messages = interview_prompts.build_replace_prompt(profile_data, jd, last_question, recent)
        elif action == "reference":
            messages = interview_prompts.build_reference_prompt(profile_data, jd, last_question, recent)
        else:
            if not user_answer:
                raise ValueError("回答不能为空")
            messages = interview_prompts.build_evaluate_prompt(
                profile_data, jd, last_question, user_answer, recent
            )
    except ValueError as exc:
        generation_guard.release(guard_key)
        return EventSourceResponse(_error(str(exc)))
    except Exception as exc:
        generation_guard.release(guard_key)
        logging.getLogger("speakwise").error("模拟面试回应准备失败: %s", exc, exc_info=True)
        return EventSourceResponse(_error(public_generation_error(exc)))

    response_content = ""
    thinking_content = ""

    async def _stream():
        nonlocal response_content, thinking_content
        try:
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
        except Exception as exc:
            logging.getLogger("speakwise").error("模拟面试回应失败: %s", exc, exc_info=True)
            yield {"event": "error", "data": public_generation_error(exc)}
        finally:
            generation_guard.release(guard_key)

    return EventSourceResponse(_stream())


@router.post("/next")
async def interview_next(request: Request, session: Session = Depends(get_session)):
    """生成下一个面试问题。body: { session_id }"""
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        return EventSourceResponse(_error("缺少 session_id"))

    profile = profile_service.get_active_profile(session)
    try:
        validate_owned_session(session, session_id, profile.id, required_mode="mock")
    except Exception as exc:
        return EventSourceResponse(_error(public_generation_error(exc)))
    guard_key = f"session:{session_id}"
    guard_error = generation_guard.try_acquire(guard_key)
    if guard_error:
        return EventSourceResponse(_error(guard_error))
    try:
        _apply_llm(session)
        profile_data, jd = _get_knowledge(session)
        await refresh_conversation_summary(session, session_id)
        recent = ContextBuilder(session).build_history_messages(session_id)
        messages = interview_prompts.build_next_question_prompt(profile_data, jd, recent)
    except Exception as exc:
        generation_guard.release(guard_key)
        logging.getLogger("speakwise").error("下一题准备失败: %s", exc, exc_info=True)
        return EventSourceResponse(_error(public_generation_error(exc)))

    question_content = ""
    thinking_content = ""

    async def _stream():
        nonlocal question_content, thinking_content
        try:
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
        except Exception as exc:
            logging.getLogger("speakwise").error("下一题生成失败: %s", exc, exc_info=True)
            yield {"event": "error", "data": public_generation_error(exc)}
        finally:
            generation_guard.release(guard_key)

    return EventSourceResponse(_stream())


@router.post("/summary")
async def interview_summary(request: Request, session: Session = Depends(get_session)):
    """生成面试汇总文档。body: { session_id }"""
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        return EventSourceResponse(_error("缺少 session_id"))

    profile = profile_service.get_active_profile(session)
    try:
        validate_owned_session(session, session_id, profile.id, required_mode="mock")
    except Exception as exc:
        return EventSourceResponse(_error(public_generation_error(exc)))
    guard_key = f"session:{session_id}"
    guard_error = generation_guard.try_acquire(guard_key)
    if guard_error:
        return EventSourceResponse(_error(guard_error))
    try:
        _apply_llm(session)
        all_msgs = session_service.list_messages(session, session_id)
        qa_list = _extract_qa(all_msgs)
        messages = interview_prompts.build_summary_prompt(qa_list)
    except Exception as exc:
        generation_guard.release(guard_key)
        logging.getLogger("speakwise").error("面试汇总准备失败: %s", exc, exc_info=True)
        return EventSourceResponse(_error(public_generation_error(exc)))
    summary_content = ""

    async def _stream():
        nonlocal summary_content
        try:
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
        except Exception as exc:
            logging.getLogger("speakwise").error("面试汇总失败: %s", exc, exc_info=True)
            yield {"event": "error", "data": public_generation_error(exc)}
        finally:
            generation_guard.release(guard_key)

    return EventSourceResponse(_stream())


# ── Helpers ──

def _get_last_question_message(db, session_id: int) -> Message | None:
    from sqlmodel import select as _sel
    msg = db.exec(
        _sel(Message)
        .where(Message.session_id == session_id)
        .where(Message.type.in_(["interview_question"]))  # type: ignore[arg-type]
        .order_by(Message.created_at.desc())
    ).first()
    return msg


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
