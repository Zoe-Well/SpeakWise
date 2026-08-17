"""Skill category definitions and LLM-backed classification helpers."""

import json
import re

from backend.src.llm.client import llm_client


SKILL_CATEGORIES: dict[str, str] = {
    "programming_language": "编程语言",
    "frontend_client": "前端与客户端",
    "backend_data": "后端与数据",
    "ai_algorithm": "AI 与算法",
    "agent_llm": "Agent 与 LLM 应用",
    "cloud_devops": "云平台与 DevOps",
    "software_engineering": "软件工程能力",
    "other": "其他",
}


def normalize_category(value: str | None) -> str:
    """Return a supported category key, falling back to ``other``."""
    if value in SKILL_CATEGORIES:
        return value
    return "other"


def category_label(value: str | None) -> str:
    """Return the display label for a category value."""
    return SKILL_CATEGORIES[normalize_category(value)]


def _without_markdown_fence(value: str) -> str:
    text = value.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else text


async def classify_existing_skills(skills: list[dict]) -> list[dict]:
    """Classify skills while preserving the input order and all input items."""
    if not skills:
        return []

    prompt = (
        "Classify each skill into exactly one of these category keys: "
        f"{json.dumps(SKILL_CATEGORIES, ensure_ascii=False)}. Unknown skills use other. "
        'Return JSON only in this shape: {"classifications": '
        '[{"id": 1, "category": "agent_llm"}]}. '
        "Do not return Markdown, explanations, or any other fields.\n\n"
        f"Skills: {json.dumps(skills, ensure_ascii=False)}"
    )
    response = await llm_client.chat(
        [{"role": "user", "content": prompt}],
        temperature=0.1,
        model=llm_client.fast_model(),
    )
    payload = json.loads(_without_markdown_fence(response))
    if not isinstance(payload, dict):
        raise ValueError("classification response must be a JSON object")
    classifications = payload.get("classifications", [])
    if not isinstance(classifications, list):
        classifications = []

    category_by_id: dict[object, str] = {}
    for item in classifications:
        if not isinstance(item, dict) or "id" not in item:
            continue
        try:
            category_by_id[item["id"]] = normalize_category(item.get("category"))
        except TypeError:
            continue

    result = []
    for skill in skills:
        result.append(
            {
                "id": skill.get("id"),
                "name": skill.get("name", ""),
                "current_category": normalize_category(skill.get("category")),
                "suggested_category": category_by_id.get(skill.get("id"), "other"),
            }
        )
    return result
