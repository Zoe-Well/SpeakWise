from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool

from backend.src.models.document import SourceDocument
from backend.src.models.job_context import JobContext
from backend.src.models.profile import UserProfile
from backend.src.models.session import ConversationSession, Message
from backend.src.services.context_builder import ContextBudgets, ContextBuilder


def _db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_context_builder_uses_only_active_jd() -> None:
    db = _db()
    profile = UserProfile(name="Zoe", is_active=True)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    db.add(JobContext(profile_id=profile.id, name="old", is_active=False, core_skills='["Java"]'))
    db.add(JobContext(profile_id=profile.id, name="active", is_active=True, core_skills='["Python"]'))
    db.commit()

    selected = ContextBuilder(db).load_active_jd(profile.id)

    assert selected is not None
    assert selected["core_skills"] == ["Python"]


def test_document_budgets_apply_to_category_total_not_each_document() -> None:
    db = _db()
    profile = UserProfile(name="Zoe", is_active=True)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    for index in range(3):
        db.add(SourceDocument(
            profile_id=profile.id,
            scope="profile",
            usage="attach",
            filename=f"doc-{index}.txt",
            file_type="txt",
            extracted_text="x" * 100,
            parse_status="success",
            is_active=True,
        ))
    db.commit()

    builder = ContextBuilder(db, ContextBudgets(profile_documents=90))
    data = builder.load_profile_data(profile.id)

    assert sum(len(doc["text"]) for doc in data["profile_docs"]) <= 90


def test_profile_and_jd_have_independent_budgets() -> None:
    builder = ContextBuilder(None, ContextBudgets(profile=40, jd=30))
    profile_data = {
        "name": "Z" * 100,
        "internships": [], "projects": [], "skills": [],
        "profile_docs": [], "jd_docs": [],
    }
    jd = {"core_skills": ["Python" * 20], "duties": [], "culture_values": []}

    assert len(builder.format_profile(profile_data, include_documents=False)) <= 40
    assert len(builder.format_jd(jd)) <= 30


def test_profile_skill_groups_use_chinese_category_labels() -> None:
    builder = ContextBuilder(None)
    profile_data = {
        "name": "Zoe",
        "internships": [],
        "projects": [],
        "skills": [
            {"category": "agent_llm", "name": "RAG", "proficiency": "熟悉"},
            {"category": "other", "name": "Git", "proficiency": "熟悉"},
            {"category": "unknown_category", "name": "Other", "proficiency": "了解"},
        ],
        "profile_docs": [],
        "jd_docs": [],
    }

    rendered = builder.format_profile(profile_data, include_documents=False)

    assert "技能-Agent 与 LLM 应用：RAG(熟悉)" in rendered
    assert rendered.count("技能-其他：") == 1
    assert "技能-其他：Git(熟悉), Other(了解)" in rendered
    assert "agent_llm" not in rendered
    assert "unknown_category" not in rendered


def test_history_contains_summary_and_recent_messages_once() -> None:
    db = _db()
    profile = UserProfile(name="Zoe", is_active=True)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    conv = ConversationSession(profile_id=profile.id, name="test")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    old_user = Message(session_id=conv.id, role="user", content="OLD-QUESTION", type="free_text")
    old_answer = Message(session_id=conv.id, role="assistant", content="OLD-ANSWER", type="free_text")
    db.add(old_user)
    db.add(old_answer)
    db.commit()
    db.refresh(old_answer)
    conv.memory_summary = "用户此前讨论过缓存一致性。"
    conv.summary_up_to_message_id = old_answer.id
    db.add(conv)
    db.commit()
    db.add(Message(session_id=conv.id, role="user", content="RECENT-QUESTION", type="free_text"))
    db.add(Message(session_id=conv.id, role="assistant", content="RECENT-ANSWER", type="free_text"))
    db.commit()

    history = ContextBuilder(db).build_history_messages(conv.id)

    joined = "\n".join(message["content"] for message in history)
    assert "缓存一致性" in joined
    assert joined.count("RECENT-QUESTION") == 1
    assert joined.count("RECENT-ANSWER") == 1


def test_technical_context_includes_each_attachment_once() -> None:
    from backend.src.prompts.technical import build_technical_messages

    profile_data = {
        "name": "Zoe",
        "internships": [],
        "projects": [],
        "skills": [],
        "profile_docs": [{"filename": "resume.txt", "text": "UNIQUE-ATTACHMENT"}],
        "jd_docs": [],
    }

    messages = build_technical_messages(profile_data, "解释事件循环")
    rendered = "\n".join(message["content"] for message in messages)

    assert rendered.count("UNIQUE-ATTACHMENT") == 1


async def _collect(iterator):
    return [item async for item in iterator]


def test_free_text_pipeline_does_not_duplicate_recent_history(monkeypatch) -> None:
    import asyncio
    from backend.src.services import conversation_service

    db = _db()
    profile = UserProfile(name="Zoe", is_active=True)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    conv = ConversationSession(profile_id=profile.id, name="history", mode="interview")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    db.add(Message(session_id=conv.id, role="user", content="PRIOR-UNIQUE", type="free_text"))
    db.add(Message(session_id=conv.id, role="assistant", content="OLD-ANSWER", type="free_text"))
    current = Message(session_id=conv.id, role="user", content="请继续", type="free_text")
    db.add(current)
    db.commit()
    db.refresh(current)
    captured: list[dict] = []

    async def fake_stream(messages, temperature=0.4, model=None):
        captured.extend(messages)
        yield {"type": "token", "content": "ok"}

    monkeypatch.setattr(conversation_service, "_native_thinking_stream", fake_stream)
    profile_data = {
        "name": "Zoe", "internships": [], "projects": [], "skills": [],
        "profile_docs": [], "jd_docs": [],
    }
    asyncio.run(_collect(conversation_service.handle_message(
        session_id=conv.id,
        content="请继续",
        command=None,
        profile_data=profile_data,
        db=db,
        session_mode="interview",
        current_message_id=current.id,
    )))

    rendered = "\n".join(message["content"] for message in captured)
    assert rendered.count("PRIOR-UNIQUE") == 1
