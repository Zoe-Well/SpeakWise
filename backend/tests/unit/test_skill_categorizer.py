import pytest

from backend.src.services import skill_categorizer


def test_normalize_category_maps_unknown_values_to_other() -> None:
    assert skill_categorizer.normalize_category("not-a-category") == "other"
    assert skill_categorizer.normalize_category(None) == "other"


@pytest.mark.asyncio
async def test_classify_existing_skills_returns_all_input_skills_in_order_for_invalid_or_missing_results(
    monkeypatch,
) -> None:
    async def fake_chat(messages, temperature=0.4, model=None):
        return '```json\n{"classifications": [{"id": 2, "category": "not-a-category"}, {"id": 99, "category": "agent_llm"}]}\n```'

    monkeypatch.setattr(skill_categorizer.llm_client, "chat", fake_chat)
    skills = [
        {"id": 1, "name": "Python"},
        {"id": 2, "name": "React"},
        {"id": 3, "name": "FastAPI"},
    ]

    result = await skill_categorizer.classify_existing_skills(skills)

    assert [skill["id"] for skill in result] == [1, 2, 3]
    assert [skill["category"] for skill in result] == ["other", "other", "other"]
    assert [skill["name"] for skill in result] == ["Python", "React", "FastAPI"]
