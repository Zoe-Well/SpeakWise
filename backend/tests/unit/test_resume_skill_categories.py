import pytest

from backend.src.api import documents
from backend.src.llm import client as llm_client_module


@pytest.mark.asyncio
async def test_resume_import_normalizes_skills_to_fixed_categories(monkeypatch) -> None:
    captured = {}

    async def fake_chat(messages, temperature=0.1, model=None):
        captured["prompt"] = messages[0]["content"]
        return (
            '{"skills": ['
            '{"category":"agent_llm","name":"LangGraph","proficiency":"熟悉"},'
            '{"category":"framework","name":"FastAPI","proficiency":"精通"}'
            ']}'
        )

    monkeypatch.setattr(llm_client_module.llm_client, "chat", fake_chat)

    proposals = await documents._llm_parse_resume("LangGraph, FastAPI")

    skill_changes = [proposal for proposal in proposals if proposal["target"] == "skill"]
    assert [change["value"]["category"] for change in skill_changes] == [
        "agent_llm",
        "other",
    ]
    assert "language|framework|tool|other" not in captured["prompt"]
    assert "\n技能 category 只能从以下固定键中选择" in captured["prompt"]
