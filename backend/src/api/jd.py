"""岗位上下文（JD）API"""

from fastapi import Body, APIRouter, Depends, HTTPException
from sqlmodel import Session, select as _sel

from backend.src.db.connection import get_session
from backend.src.services.jd_analyzer import analyze_jd
from backend.src.models.job_context import JobContext
from backend.src.models.session import ConversationSession
from backend.src.services import profile_service

router = APIRouter(prefix="/api", tags=["jd"])


@router.get("/jd/latest")
def get_latest_jd(session: Session = Depends(get_session)):
    """获取当前 profile 最新的 JD 分析结果。"""
    profile = profile_service.get_or_create_profile(session)
    jc = session.exec(
        _sel(JobContext)
        .where(JobContext.profile_id == profile.id)
        .order_by(JobContext.id.desc())
    ).first()
    if not jc:
        return {"found": False}
    return {
        "found": True,
        "jd_context_id": jc.id,
        "raw_text": jc.raw_text,
        "core_skills": jc.to_analysis_dict()["core_skills"],
        "duties": jc.to_analysis_dict()["duties"],
        "culture_values": jc.to_analysis_dict()["culture_values"],
    }


@router.post("/jd/analyze")
async def analyze_jd_endpoint(data: dict = Body(None), session: Session = Depends(get_session)):
    """解析岗位描述文本并持久化。

    请求: { raw_text, session_id? }
    - session_id 可选：传入则自动关联 JD 到该会话
    """
    text = (data or {}).get("raw_text", "")
    session_id = (data or {}).get("session_id")

    if not text:
        return {"parse_status": "failed", "core_skills": [], "duties": [], "culture_values": [],
                "error": "empty input"}

    result = await analyze_jd(text)
    if result.get("parse_error"):
        return {"parse_status": "failed", "core_skills": [], "duties": [], "culture_values": [],
                "error": result["parse_error"]}

    # 持久化 JD 分析结果
    profile = profile_service.get_or_create_profile(session)
    jc = JobContext.from_analysis(profile.id, text, result)
    session.add(jc)
    session.commit()
    session.refresh(jc)

    # 如果提供了 session_id，关联到该会话
    if session_id:
        conv = session.get(ConversationSession, session_id)
        if conv:
            conv.jd_context_id = jc.id
            from datetime import datetime
            conv.updated_at = datetime.utcnow()
            session.add(conv)
            session.commit()

    return {
        "parse_status": "success",
        "jd_context_id": jc.id,
        "core_skills": result.get("core_skills", []),
        "duties": result.get("duties", []),
        "culture_values": result.get("culture_values", []),
    }


@router.put("/jd/{jd_context_id}")
def update_jd(jd_context_id: int, data: dict = Body(...), session: Session = Depends(get_session)):
    """更新已有的 JD 分析结果（支持手动修正 skills/duties/values）。"""
    profile = profile_service.get_or_create_profile(session)
    jc = session.get(JobContext, jd_context_id)
    if not jc or jc.profile_id != profile.id:
        raise HTTPException(404)
    import json as _json
    for field in ("core_skills", "duties", "culture_values"):
        if field in data:
            setattr(jc, field, _json.dumps(data[field], ensure_ascii=False))
    session.add(jc)
    session.commit()
    return {"ok": True, "jd_context_id": jc.id}
