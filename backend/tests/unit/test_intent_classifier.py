import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from backend.src.models.session import ConversationSession, Message
from backend.src.services import conversation_service


def _db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_explicit_command_has_highest_priority() -> None:
    assert conversation_service.classify_interview_intent(
        "/scenario 请解释 Redis 原理"
    ) == "/scenario"


def test_weighted_rules_distinguish_technical_and_scenario_questions() -> None:
    assert conversation_service.classify_interview_intent(
        "Redis 和 MongoDB 有什么区别"
    ) == "/technical"
    assert conversation_service.classify_interview_intent(
        "你会怎么处理团队冲突"
    ) == "/scenario"


def test_weak_or_conflicting_rules_defer_classification() -> None:
    assert conversation_service.classify_interview_intent("这个应该如何回答") is None
    assert conversation_service.classify_interview_intent("项目中的 Redis 挑战") is None


@pytest.mark.asyncio
async def test_short_followup_inherits_recent_interview_intent(monkeypatch) -> None:
    db = _db()
    conversation = ConversationSession(profile_id=1, name="intent", mode="interview")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    db.add(Message(
        session_id=conversation.id,
        role="assistant",
        command="/scenario",
        content="请描述一次团队冲突。",
        type="scenario",
    ))
    db.commit()

    async def unexpected_chat(*_args, **_kwargs):
        raise AssertionError("short follow-up should not call the model classifier")

    monkeypatch.setattr(conversation_service.llm_client, "chat", unexpected_chat)

    intent = await conversation_service.classify_interview_intent_hybrid(
        "那后来呢", db=db, session_id=conversation.id
    )

    assert intent == "/scenario"


@pytest.mark.asyncio
async def test_ambiguous_message_uses_fast_model_classifier(monkeypatch) -> None:
    called = {}

    async def fake_chat(*_args, **kwargs):
        called["model"] = kwargs["model"]
        return '{"intent":"technical","confidence":0.92}'

    monkeypatch.setattr(conversation_service.llm_client, "chat", fake_chat)

    intent = await conversation_service.classify_interview_intent_hybrid(
        "请帮我分析这个问题"
    )

    assert intent == "/technical"
    assert called["model"] == conversation_service.llm_client.fast_model()
