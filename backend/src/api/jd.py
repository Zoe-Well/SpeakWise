"""岗位上下文（JD）API"""

from fastapi import Body, APIRouter, Depends, HTTPException
from sqlmodel import Session, select as _sel

from backend.src.db.connection import get_session
from backend.src.services.jd_analyzer import analyze_jd
from backend.src.models.job_context import JobContext
from backend.src.models.session import ConversationSession
from backend.src.services import profile_service

router = APIRouter(prefix="/api", tags=["jd"])


# ── JD List & Management ─────────────────────────────────

@router.get("/jd/list")
def list_jd_contexts(session: Session = Depends(get_session)):
    """列出当前活跃简历下的所有 JD 上下文。"""
    profile = profile_service.get_active_profile(session)
    rows = session.exec(
        _sel(JobContext)
        .where(JobContext.profile_id == profile.id)
        .order_by(JobContext.created_at.desc())
    ).all()
    return [{
        "id": jc.id, "name": jc.name or f"JD #{jc.id}",
        "is_active": jc.is_active,
        "core_skills": jc.to_analysis_dict()["core_skills"],
        "duties": jc.to_analysis_dict()["duties"],
        "culture_values": jc.to_analysis_dict()["culture_values"],
        "created_at": jc.created_at.isoformat() if jc.created_at else None,
    } for jc in rows]


@router.post("/jd/{jd_id}/activate")
def activate_jd(jd_id: int, session: Session = Depends(get_session)):
    """激活指定 JD，同时取消同 profile 下其他 JD 的激活状态。"""
    profile = profile_service.get_active_profile(session)
    jc = session.get(JobContext, jd_id)
    if not jc or jc.profile_id != profile.id:
        raise HTTPException(404, "JD 记录不存在")

    # Deactivate all JDs under this profile
    all_jds = session.exec(
        _sel(JobContext).where(JobContext.profile_id == profile.id)
    ).all()
    for j in all_jds:
        j.is_active = (j.id == jd_id)
        session.add(j)
    session.commit()
    return {"ok": True, "jd_context_id": jd_id}


@router.post("/jd/deactivate")
def deactivate_all_jds(session: Session = Depends(get_session)):
    """取消所有 JD 的激活状态（设为"不使用 JD"）。"""
    profile = profile_service.get_active_profile(session)
    all_jds = session.exec(
        _sel(JobContext).where(JobContext.profile_id == profile.id)
    ).all()
    for j in all_jds:
        j.is_active = False
        session.add(j)
    session.commit()
    return {"ok": True}


@router.delete("/jd/{jd_id}")
def delete_jd(jd_id: int, session: Session = Depends(get_session)):
    """删除指定 JD 上下文。"""
    profile = profile_service.get_active_profile(session)
    jc = session.get(JobContext, jd_id)
    if not jc or jc.profile_id != profile.id:
        raise HTTPException(404, "JD 记录不存在")
    session.delete(jc)
    session.commit()
    return {"ok": True}


# ── JD Analysis ──────────────────────────────────────────

@router.get("/jd/latest")
def get_latest_jd(session: Session = Depends(get_session)):
    """获取当前活跃简历下激活的 JD 分析结果（is_active=True）。"""
    profile = profile_service.get_active_profile(session)
    jc = session.exec(
        _sel(JobContext)
        .where(JobContext.profile_id == profile.id)
        .where(JobContext.is_active == True)  # noqa: E712
        .order_by(JobContext.id.desc())
    ).first()
    if not jc:
        return {"found": False}
    return {
        "found": True,
        "jd_context_id": jc.id,
        "name": jc.name,
        "raw_text": jc.raw_text,
        "core_skills": jc.to_analysis_dict()["core_skills"],
        "duties": jc.to_analysis_dict()["duties"],
        "culture_values": jc.to_analysis_dict()["culture_values"],
    }


@router.post("/jd/analyze")
async def analyze_jd_endpoint(data: dict = Body(None), session: Session = Depends(get_session)):
    """解析岗位描述文本并持久化，自动激活新 JD。

    请求: { raw_text, name?, session_id? }
    """
    text = (data or {}).get("raw_text", "")
    jd_name = (data or {}).get("name", "").strip()
    session_id = (data or {}).get("session_id")

    if not text:
        return {"parse_status": "failed", "core_skills": [], "duties": [], "culture_values": [],
                "error": "empty input"}

    result = await analyze_jd(text)
    if result.get("parse_error"):
        return {"parse_status": "failed", "core_skills": [], "duties": [], "culture_values": [],
                "error": result["parse_error"]}

    # 持久化 JD 分析结果
    profile = profile_service.get_active_profile(session)

    # Deactivate existing JDs so new one becomes the active one
    existing = session.exec(
        _sel(JobContext).where(JobContext.profile_id == profile.id)
    ).all()
    for j in existing:
        j.is_active = False
        session.add(j)

    jc = JobContext.from_analysis(profile.id, text, result)
    jc.is_active = True
    if jd_name:
        jc.name = jd_name
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
        "name": jc.name,
        "core_skills": result.get("core_skills", []),
        "duties": result.get("duties", []),
        "culture_values": result.get("culture_values", []),
    }


@router.put("/jd/{jd_context_id}")
def update_jd(jd_context_id: int, data: dict = Body(...), session: Session = Depends(get_session)):
    """更新已有的 JD 分析结果（支持 name + skills/duties/values 手动修正）。"""
    profile = profile_service.get_active_profile(session)
    jc = session.get(JobContext, jd_context_id)
    if not jc or jc.profile_id != profile.id:
        raise HTTPException(404)
    import json as _json
    for field in ("core_skills", "duties", "culture_values"):
        if field in data:
            setattr(jc, field, _json.dumps(data[field], ensure_ascii=False))
    if "name" in data:
        jc.name = str(data["name"])[:200]
    session.add(jc)
    session.commit()
    return {"ok": True, "jd_context_id": jc.id}
