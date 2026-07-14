"""会话与消息 API 路由"""

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlmodel import Session

from backend.src.db.connection import get_session
from backend.src.models.session import ConversationSession
from backend.src.services import profile_service, session_service

router = APIRouter(prefix="/api", tags=["sessions"])


@router.get("/sessions")
def list_sessions(session: Session = Depends(get_session)):
    profile = profile_service.get_or_create_profile(session)
    items = session_service.list_sessions(session, profile.id)
    return [{"id": s.id, "name": s.name, "mode": s.mode,
             "jd_context_id": s.jd_context_id,
             "active_template_id": s.active_template_id,
             "created_at": s.created_at.isoformat(), "updated_at": s.updated_at.isoformat()} for s in items]


@router.post("/sessions")
def create_session(data: dict = Body(...), session: Session = Depends(get_session)):
    profile = profile_service.get_or_create_profile(session)
    s = session_service.create_session(session, profile.id, data.get("name", "新会话"),
                                        mode=data.get("mode", "normal"))
    return {"id": s.id, "name": s.name, "mode": s.mode}


@router.put("/sessions/{session_id}")
def update_session(session_id: int, data: dict, session: Session = Depends(get_session)):
    s = session_service.update_session(session, session_id, data)
    if not s: raise HTTPException(404)
    return {"id": s.id, "name": s.name}


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, session: Session = Depends(get_session)):
    profile = profile_service.get_or_create_profile(session)
    conv = session.get(ConversationSession, session_id)
    if not conv or conv.profile_id != profile.id:
        raise HTTPException(404)
    if not session_service.delete_session(session, session_id):
        raise HTTPException(404)
    return {"ok": True}


@router.get("/sessions/{session_id}/messages")
def list_messages(session_id: int, before: str = None, session: Session = Depends(get_session)):
    msgs = session_service.list_messages(session, session_id, before)
    return [{"id": m.id, "role": m.role, "command": m.command, "content": m.content,
             "thinking": m.thinking, "type": m.type, "created_at": m.created_at.isoformat()} for m in msgs]


@router.post("/sessions/batch-delete")
def batch_delete_sessions(data: dict = Body(...), session: Session = Depends(get_session)):
    """批量删除会话。body: { ids: [1, 2, 3] }"""
    ids = data.get("ids", [])
    deleted = 0
    for sid in ids:
        if session_service.delete_session(session, sid):
            deleted += 1
    return {"deleted": deleted}


@router.delete("/sessions/{session_id}/messages/{message_id}")
def delete_message(session_id: int, message_id: int, session: Session = Depends(get_session)):
    """删除单条消息。如果是用户消息，同时删除紧随其后的 AI 回复。"""
    from backend.src.models.session import Message
    msg = session.get(Message, message_id)
    if not msg or msg.session_id != session_id:
        raise HTTPException(404, "消息不存在")
    # Find and delete paired message (user+AI pair)
    to_delete = [msg]
    if msg.role == "user":
        # Find the next assistant message (the AI response)
        next_msg = session.exec(
            __import__("sqlmodel").select(Message).where(
                Message.session_id == session_id,
                Message.id > message_id,
                Message.role == "assistant"
            ).order_by(Message.id).limit(1)
        ).first()
        if next_msg:
            to_delete.append(next_msg)
    for m in to_delete:
        session.delete(m)
    session.commit()
    return {"deleted": len(to_delete)}
