import pytest

from backend.src.services import skill_categorizer


def test_normalize_category_maps_unknown_values_to_other() -> None:
    assert skill_categorizer.normalize_category("not-a-category") == "other"
    assert skill_categorizer.normalize_category(None) == "other"


def test_category_labels_match_product_copy() -> None:
    assert skill_categorizer.SKILL_CATEGORIES == {
        "programming_language": "编程语言",
        "frontend_client": "前端与客户端",
        "backend_data": "后端与数据",
        "ai_algorithm": "AI 与算法",
        "agent_llm": "Agent 与 LLM 应用",
        "cloud_devops": "云平台与 DevOps",
        "software_engineering": "软件工程能力",
        "other": "其他",
    }


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
    assert result == [
        {"id": 1, "name": "Python", "current_category": "other", "suggested_category": "other"},
        {"id": 2, "name": "React", "current_category": "other", "suggested_category": "other"},
        {"id": 3, "name": "FastAPI", "current_category": "other", "suggested_category": "other"},
    ]


@pytest.mark.asyncio
async def test_classification_uses_normalized_current_and_suggested_categories(monkeypatch) -> None:
    captured = {}

    async def fake_chat(messages, temperature=0.4, model=None):
        captured["prompt"] = messages[0]["content"]
        return '{"classifications": [{"id": 2, "category": "agent_llm"}, {"id": [3], "category": "backend_data"}]}'

    monkeypatch.setattr(skill_categorizer.llm_client, "chat", fake_chat)
    result = await skill_categorizer.classify_existing_skills([
        {"id": 1, "name": "Python", "category": "programming_language"},
        {"id": 2, "name": "LangGraph", "category": "unknown"},
        {"id": 3, "name": "FastAPI"},
    ])

    assert result == [
        {"id": 1, "name": "Python", "current_category": "programming_language", "suggested_category": "other"},
        {"id": 2, "name": "LangGraph", "current_category": "other", "suggested_category": "agent_llm"},
        {"id": 3, "name": "FastAPI", "current_category": "other", "suggested_category": "other"},
    ]
    assert "前端与客户端" in captured["prompt"]


@pytest.mark.asyncio
async def test_classification_propagates_llm_and_json_errors(monkeypatch) -> None:
    async def failing_chat(*args, **kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(skill_categorizer.llm_client, "chat", failing_chat)
    with pytest.raises(RuntimeError, match="llm unavailable"):
        await skill_categorizer.classify_existing_skills([{"id": 1, "name": "Python"}])

    async def invalid_chat(*args, **kwargs):
        return "not json"

    monkeypatch.setattr(skill_categorizer.llm_client, "chat", invalid_chat)
    with pytest.raises(ValueError):
        await skill_categorizer.classify_existing_skills([{"id": 1, "name": "Python"}])
