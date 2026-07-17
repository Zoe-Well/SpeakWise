"""知识库 API 路由"""

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlmodel import Session

from backend.src.db.connection import get_session
from backend.src.services import profile_service

router = APIRouter(prefix="/api", tags=["profile"])


# ── Resume Management (Multi-Profile) ─────────────────────

@router.get("/resumes")
def list_resumes(session: Session = Depends(get_session)):
    """列出所有简历（含统计信息）。"""
    return profile_service.list_profiles(session)


@router.post("/resumes")
def create_resume(data: dict = Body(...), session: Session = Depends(get_session)):
    """创建新简历。"""
    if not data.get("name"):
        raise HTTPException(422, "name 为必填")
    profile = profile_service.create_profile(session, data)
    return _profile_out(profile, session)


@router.put("/resumes/{profile_id}")
def update_resume(profile_id: int, data: dict = Body(...), session: Session = Depends(get_session)):
    """更新简历基本信息。"""
    try:
        profile = profile_service.update_profile(session, data, profile_id=profile_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return _profile_out(profile, session)


@router.delete("/resumes/{profile_id}")
def delete_resume(profile_id: int, session: Session = Depends(get_session)):
    """删除简历（禁止删除最后一个）。"""
    try:
        ok = profile_service.delete_profile(session, profile_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not ok:
        raise HTTPException(404, "记录不存在")
    return {"ok": True}


@router.post("/resumes/{profile_id}/activate")
def activate_resume(profile_id: int, session: Session = Depends(get_session)):
    """激活指定简历。"""
    try:
        profile = profile_service.activate_profile(session, profile_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return _profile_out(profile, session)


@router.get("/profile/active")
def get_active_profile_endpoint(session: Session = Depends(get_session)):
    """获取当前活跃简历的完整数据。"""
    profile = profile_service.get_active_profile(session)
    return _profile_full(profile, session)


# ── Profile (Backward Compatible) ──────────────────────────

@router.get("/profile")
def get_profile(session: Session = Depends(get_session)):
    profile = profile_service.get_active_profile(session)
    return _profile_out(profile, session)


@router.put("/profile/{profile_id}")
def update_profile_endpoint(profile_id: int, data: dict = Body(...), session: Session = Depends(get_session)):
    try:
        profile = profile_service.update_profile(session, data, profile_id=profile_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return _profile_out(profile, session)


# ── Experiences ──────────────────────────────────────────

@router.get("/experiences")
def list_experiences(type: str = "internship", session: Session = Depends(get_session)):
    profile = profile_service.get_active_profile(session)
    if type == "internship":
        items = profile_service.list_internships(session, profile.id)
        return [_internship_out(i) for i in items]
    else:
        items = profile_service.list_projects(session, profile.id)
        return [_project_out(p) for p in items]


@router.post("/experiences")
def create_experience(type: str, data: dict, session: Session = Depends(get_session)):
    profile = profile_service.get_active_profile(session)
    if type == "internship":
        if not data.get("company") or not data.get("position"):
            raise HTTPException(422, "company 和 position 为必填")
        return _internship_out(profile_service.create_internship(session, profile.id, data))
    else:
        if not data.get("name"):
            raise HTTPException(422, "name 为必填")
        return _project_out(profile_service.create_project(session, profile.id, data))


@router.put("/experiences/{item_id}")
def update_experience(item_id: int, type: str, data: dict, session: Session = Depends(get_session)):
    if type == "internship":
        item = profile_service.update_internship(session, item_id, data)
    else:
        item = profile_service.update_project(session, item_id, data)
    if not item:
        raise HTTPException(404, "记录不存在")
    return item


@router.delete("/experiences/{item_id}")
def delete_experience(item_id: int, type: str, session: Session = Depends(get_session)):
    ok = (profile_service.delete_internship(session, item_id) if type == "internship"
          else profile_service.delete_project(session, item_id))
    if not ok:
        raise HTTPException(404, "记录不存在")
    return {"ok": True}


# ── Skills ───────────────────────────────────────────────

@router.get("/skills")
def list_skills_endpoint(session: Session = Depends(get_session)):
    profile = profile_service.get_active_profile(session)
    return [_skill_out(s) for s in profile_service.list_skills(session, profile.id)]


@router.post("/skills")
def create_skill_endpoint(data: dict = Body(...), session: Session = Depends(get_session)):
    profile = profile_service.get_active_profile(session)
    if not data.get("category") or not data.get("name"):
        raise HTTPException(422, "category 和 name 为必填")
    return _skill_out(profile_service.create_skill(session, profile.id, data))


@router.put("/skills/{item_id}")
def update_skill_endpoint(item_id: int, data: dict, session: Session = Depends(get_session)):
    item = profile_service.update_skill(session, item_id, data)
    if not item:
        raise HTTPException(404, "记录不存在")
    return _skill_out(item)


@router.delete("/skills/{item_id}")
def delete_skill_endpoint(item_id: int, session: Session = Depends(get_session)):
    if not profile_service.delete_skill(session, item_id):
        raise HTTPException(404, "记录不存在")
    return {"ok": True}


# ── Output helpers ───────────────────────────────────────

def _profile_out(p, s):
    import json
    return {
        "id": p.id, "name": p.name, "phone": p.phone, "email": p.email,
        "is_active": p.is_active,
        "internship_count": len(profile_service.list_internships(s, p.id)),
        "project_count": len(profile_service.list_projects(s, p.id)),
        "skill_count": len(profile_service.list_skills(s, p.id)),
    }

def _profile_full(p, s):
    """返回活跃简历的完整数据（含子表）。"""
    import json
    return {
        "id": p.id, "name": p.name, "phone": p.phone, "email": p.email, "is_active": p.is_active,
        "internships": [_internship_out(i) for i in profile_service.list_internships(s, p.id)],
        "projects": [_project_out(pr) for pr in profile_service.list_projects(s, p.id)],
        "skills": [_skill_out(sk) for sk in profile_service.list_skills(s, p.id)],
    }

def _internship_out(i):
    return {"id": i.id, "profile_id": i.profile_id, "company": i.company,
            "position": i.position, "start_date": i.start_date, "end_date": i.end_date,
            "achievements": __import__("json").loads(i.achievements or "[]")}

def _project_out(p):
    return {"id": p.id, "profile_id": p.profile_id, "type": p.type, "name": p.name,
            "role": p.role, "tech_stack": __import__("json").loads(p.tech_stack or "[]"),
            "challenge": p.challenge, "solution": p.solution, "result": p.result}

def _skill_out(s):
    return {"id": s.id, "profile_id": s.profile_id, "category": s.category,
            "name": s.name, "proficiency": s.proficiency}

def _edu_out(e):
    return {"id": e.id, "profile_id": e.profile_id, "school": e.school,
            "degree": e.degree, "major": e.major, "start_date": e.start_date,
            "end_date": e.end_date}
