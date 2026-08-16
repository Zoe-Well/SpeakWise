from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

import backend.src.api.generate as generate_api
from backend.src.db.connection import get_session
from backend.src.models.profile import UserProfile
from backend.src.models.session import ConversationSession, Message


def test_generate_keeps_database_session_alive_for_sse(monkeypatch) -> None:
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)

    with Session(test_engine) as db:
        profile = UserProfile(name="测试用户", is_active=True)
        db.add(profile)
        db.commit()
        db.refresh(profile)
        conversation = ConversationSession(
            profile_id=profile.id, name="测试会话", mode="normal"
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        conversation_id = conversation.id

    def override_session():
        with Session(test_engine) as db:
            yield db

    async def fake_handle_message(**_kwargs):
        yield {"type": "meta", "model": "test", "fast_mode": True}
        yield {"type": "token", "content": "测试成功"}

    monkeypatch.setattr(generate_api, "engine", test_engine)
    monkeypatch.setattr(
        generate_api.conversation_service, "handle_message", fake_handle_message
    )

    app = FastAPI()
    app.include_router(generate_api.router)
    app.dependency_overrides[get_session] = override_session

    response = TestClient(app).post(
        "/api/generate",
        json={"session_id": conversation_id, "content": "测试"},
    )

    assert response.status_code == 200
    assert "event: token" in response.text
    assert "data: 测试成功" in response.text
    assert "event: done" in response.text

    with Session(test_engine) as db:
        messages = list(
            db.exec(
                select(Message)
                .where(Message.session_id == conversation_id)
                .order_by(Message.id)
            ).all()
        )
        assert [message.role for message in messages] == ["user", "assistant"]
        assert messages[-1].content == "测试成功"
