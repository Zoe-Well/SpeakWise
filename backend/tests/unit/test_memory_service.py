import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from backend.src.models.profile import UserProfile
from backend.src.models.session import ConversationSession, Message
from backend.src.services import memory_service


def _db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


@pytest.mark.asyncio
async def test_refresh_summary_persists_old_messages_and_keeps_recent_window(monkeypatch) -> None:
    db = _db()
    profile = UserProfile(name="Zoe", is_active=True)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    conversation = ConversationSession(profile_id=profile.id, name="memory")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    for index in range(12):
        db.add(Message(
            session_id=conversation.id,
            role="user" if index % 2 == 0 else "assistant",
            content=f"message-{index}",
            type="free_text",
        ))
    db.commit()

    async def fake_chat(*args, **kwargs):
        return "用户正在准备后端工程师面试，讨论了 message-0 到 message-3。"

    monkeypatch.setattr(memory_service.llm_client, "chat", fake_chat)

    summary = await memory_service.refresh_conversation_summary(db, conversation.id)
    db.refresh(conversation)

    assert summary == conversation.memory_summary
    assert conversation.summary_up_to_message_id is not None
    history = select(Message).where(
        Message.session_id == conversation.id,
        Message.id > conversation.summary_up_to_message_id,
    )
    assert len(db.exec(history).all()) == 8
