"""会话与消息服务"""

from typing import Optional
from sqlmodel import Session, select, desc

from backend.src.models.session import ConversationSession, Message


def create_session(session: Session, profile_id: int, name: str, mode: str = "normal", jd_context_id: Optional[int] = None) -> ConversationSession:
    s = ConversationSession(profile_id=profile_id, name=name, mode=mode, jd_context_id=jd_context_id)
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def list_sessions(session: Session, profile_id: int) -> list[ConversationSession]:
    return list(session.exec(
        select(ConversationSession).where(ConversationSession.profile_id == profile_id).order_by(desc(ConversationSession.updated_at))
    ).all())


def get_session(session: Session, session_id: int) -> Optional[ConversationSession]:
    return session.get(ConversationSession, session_id)


def update_session(session: Session, session_id: int, data: dict) -> Optional[ConversationSession]:
    s = session.get(ConversationSession, session_id)
    if not s: return None
    for key in ("name", "jd_context_id", "active_template_id"):
        if key in data: setattr(s, key, data[key])
    from datetime import datetime
    s.updated_at = datetime.utcnow()
    session.add(s); session.commit(); session.refresh(s)
    return s


def delete_session(session: Session, session_id: int) -> bool:
    s = session.get(ConversationSession, session_id)
    if not s: return False
    # Cascade delete messages
    msgs = session.exec(select(Message).where(Message.session_id == session_id)).all()
    for m in msgs: session.delete(m)
    session.delete(s); session.commit()
    return True


def add_message(session: Session, session_id: int, role: str, content: str, msg_type: str = "free_text", command: Optional[str] = None, thinking: Optional[str] = None) -> Message:
    m = Message(session_id=session_id, role=role, content=content, type=msg_type, command=command, thinking=thinking)
    session.add(m); session.commit(); session.refresh(m)
    # Bump session updated_at
    s = session.get(ConversationSession, session_id)
    if s:
        from datetime import datetime
        s.updated_at = datetime.utcnow(); session.add(s); session.commit()
    return m


def list_messages(session: Session, session_id: int, before_ts: Optional[str] = None, limit: int = 50) -> list[Message]:
    stmt = select(Message).where(Message.session_id == session_id).order_by(desc(Message.created_at)).limit(limit)
    return list(session.exec(stmt).all())[::-1]  # Reverse to chronological
