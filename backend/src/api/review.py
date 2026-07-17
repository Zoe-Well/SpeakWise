"""简历评审 API —— SSE 流式端点"""

import json
from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse
from sqlmodel import Session, select as _sel

from backend.src.db.connection import get_session
from backend.src.services import profile_service, conversation_service
from backend.src.llm.client import llm_client
from backend.src.models.job_context import JobContext

router = APIRouter(prefix="/api/review", tags=["review"])


def _get_knowledge_data(session: Session) -> tuple[dict, dict | None]:
    """获取当前活跃知识库：profile_data + jd_analysis。"""
    profile = profile_service.get_active_profile(session)
    profile_data = conversation_service.build_profile_data_for_prompt(session, profile.id)

    jd_analysis = None
    jc = session.exec(
        _sel(JobContext)
        .where(JobContext.profile_id == profile.id)
        .where(JobContext.is_active == True)  # noqa: E712
        .order_by(JobContext.id.desc())
    ).first()
    if jc:
        jd_analysis = jc.to_analysis_dict()

    return profile_data, jd_analysis


async def _stream_llm(messages: list[dict], temperature: float = 0.4):
    """SSE 流式输出 LLM 响应，格式与 generate.py 一致。"""
    full_response = ""
    full_thinking = ""

    # Emit knowledge base summary as thinking
    yield {"event": "thinking", "data": "正在基于当前选中的简历与岗位信息进行分析...\n\n"}

    async for chunk in llm_client.stream(messages, temperature=temperature):
        chunk_type = chunk.get("type", "token")
        text = chunk.get("content", "")
        if chunk_type == "thinking":
            full_thinking += text
            yield {"event": "thinking", "data": text}
        else:
            full_response += text
            yield {"event": "token", "data": text}

    yield {"event": "done", "data": json.dumps({
        "content": full_response,
        "length": len(full_response),
    }, ensure_ascii=False)}


@router.post("/resume")
async def review_resume(request: Request, session: Session = Depends(get_session)):
    """简历评审：综合评估简历结构、量化、匹配度，给出具体改进建议。"""
    from backend.src.prompts.resume_review import build_resume_review_messages

    # Reconfigure LLM from user settings
    _apply_llm_settings(session)

    profile_data, jd_analysis = _get_knowledge_data(session)
    messages = build_resume_review_messages(profile_data, jd_analysis)

    async def _stream():
        async for event in _stream_llm(messages, temperature=0.4):
            yield event

    return EventSourceResponse(_stream())


@router.post("/job")
async def analyze_job(request: Request, session: Session = Depends(get_session)):
    """岗位解析：深度解读 JD + 面试策略 + 简历匹配分析 + STAR 话术建议。"""
    from backend.src.prompts.job_analysis import build_job_analysis_messages

    # Reconfigure LLM from user settings
    _apply_llm_settings(session)

    profile_data, jd_analysis = _get_knowledge_data(session)
    messages = build_job_analysis_messages(profile_data, jd_analysis)

    async def _stream():
        async for event in _stream_llm(messages, temperature=0.4):
            yield event

    return EventSourceResponse(_stream())


def _apply_llm_settings(db):
    """从数据库加载活跃 API Key 配置到 LLM 客户端。"""
    from backend.src.api.settings import get_active_apikey, LLM_PROVIDERS
    active = get_active_apikey(db)
    if active and active["api_key"]:
        provider = LLM_PROVIDERS.get(active["provider"])
        base_url = provider["base_url"] if provider else None
        llm_client.configure(
            api_key=active["api_key"],
            base_url=base_url,
            model=active.get("model") or None,
        )
    else:
        llm_client.configure(api_key="", base_url=None, model=None)
