from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from backend.src.api import profile as profile_api
from backend.src.db.connection import get_session
from backend.src.models.profile import Skill, UserProfile
from backend.src.services import skill_categorizer


@pytest.fixture
def skill_api() -> Generator[tuple[TestClient, Session, UserProfile, UserProfile], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    active = UserProfile(name="活跃简历", is_active=True)
    other = UserProfile(name="另一份简历", is_active=False)
    session.add(active)
    session.add(other)
    session.commit()
    session.refresh(active)
    session.refresh(other)

    app = FastAPI()
    app.include_router(profile_api.router)

    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as client:
        yield client, session, active, other
    app.dependency_overrides.clear()
    session.close()


def test_preview_returns_suggestions_without_changing_database_category(skill_api, monkeypatch) -> None:
    client, session, active, _ = skill_api
    skill = Skill(
        profile_id=active.id,
        category="backend_data",
        name="数据库中的 RAG 名称",
        proficiency="熟悉",
    )
    session.add(skill)
    session.commit()
    session.refresh(skill)

    async def classify(skills: list[dict]) -> list[dict]:
        assert skills == [{
            "id": skill.id,
            "name": "数据库中的 RAG 名称",
            "category": "backend_data",
        }]
        return [{
            "id": skill.id,
            "name": "数据库中的 RAG 名称",
            "current_category": "backend_data",
            "suggested_category": "agent_llm",
        }]

    monkeypatch.setattr(skill_categorizer, "classify_existing_skills", classify)

    response = client.post(
        "/api/skills/classification/preview",
        json={"skills": [{"id": skill.id, "name": "前端传来的名称"}]},
    )

    assert response.status_code == 200
    assert response.json() == [{
        "id": skill.id,
        "name": "数据库中的 RAG 名称",
        "current_category": "backend_data",
        "suggested_category": "agent_llm",
    }]
    session.refresh(skill)
    assert skill.category == "backend_data"


def test_apply_rejects_other_profile_skill_without_partial_update(skill_api) -> None:
    client, session, active, other = skill_api
    active_skill = Skill(
        profile_id=active.id,
        category="backend_data",
        name="FastAPI",
        proficiency="熟悉",
    )
    other_skill = Skill(
        profile_id=other.id,
        category="frontend_client",
        name="React",
        proficiency="熟悉",
    )
    session.add(active_skill)
    session.add(other_skill)
    session.commit()
    session.refresh(active_skill)
    session.refresh(other_skill)

    response = client.post(
        "/api/skills/classification/apply",
        json={
            "assignments": [
                {"id": active_skill.id, "category": "agent_llm"},
                {"id": other_skill.id, "category": "cloud_devops"},
            ]
        },
    )

    assert response.status_code == 422
    session.refresh(active_skill)
    session.refresh(other_skill)
    assert active_skill.category == "backend_data"
    assert other_skill.category == "frontend_client"


def test_apply_persists_multiple_categories_in_one_commit_and_returns_updates(skill_api, monkeypatch) -> None:
    client, session, active, _ = skill_api
    first_skill = Skill(
        profile_id=active.id,
        category="other",
        name="LangGraph",
        proficiency="熟悉",
    )
    second_skill = Skill(
        profile_id=active.id,
        category="other",
        name="Docker",
        proficiency="熟悉",
    )
    session.add(first_skill)
    session.add(second_skill)
    session.commit()
    session.refresh(first_skill)
    session.refresh(second_skill)

    original_commit = session.commit
    commit_count = 0

    def track_commit() -> None:
        nonlocal commit_count
        commit_count += 1
        original_commit()

    monkeypatch.setattr(session, "commit", track_commit)
    response = client.post(
        "/api/skills/classification/apply",
        json={
            "assignments": [
                {"id": first_skill.id, "category": "agent_llm"},
                {"id": second_skill.id, "category": "cloud_devops"},
            ]
        },
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [first_skill.id, second_skill.id]
    assert [item["category"] for item in response.json()] == ["agent_llm", "cloud_devops"]
    assert commit_count == 1
    session.refresh(first_skill)
    session.refresh(second_skill)
    assert [first_skill.category, second_skill.category] == ["agent_llm", "cloud_devops"]


def test_apply_rejects_non_list_assignments(skill_api) -> None:
    client, _, _, _ = skill_api

    response = client.post(
        "/api/skills/classification/apply",
        json={"assignments": {"id": 1, "category": "agent_llm"}},
    )

    assert response.status_code == 422


@pytest.mark.parametrize("error", [RuntimeError("provider raw response"), ValueError("invalid JSON")])
def test_preview_converts_classification_errors_to_sanitized_502(skill_api, monkeypatch, error) -> None:
    client, session, active, _ = skill_api
    skill = Skill(
        profile_id=active.id,
        category="backend_data",
        name="RAG",
        proficiency="熟悉",
    )
    session.add(skill)
    session.commit()
    session.refresh(skill)

    async def fail_classification(skills: list[dict]) -> list[dict]:
        raise error

    monkeypatch.setattr(skill_categorizer, "classify_existing_skills", fail_classification)
    response = client.post(
        "/api/skills/classification/preview",
        json={"skills": [{"id": skill.id, "name": skill.name}]},
    )

    assert response.status_code == 502
    assert "provider raw response" not in response.text
    assert "invalid JSON" not in response.text
