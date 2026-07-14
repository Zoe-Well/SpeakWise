"""知识库服务层：Profile / Internship / Project / Skill CRUD"""

from typing import Optional
from sqlmodel import Session, select
from backend.src.models.profile import UserProfile, Internship, Project, Skill


def get_or_create_profile(session: Session) -> UserProfile:
    """获取第一个 UserProfile，若不存在则创建默认档案。"""
    profile = session.exec(select(UserProfile)).first()
    if not profile:
        profile = UserProfile(name="未命名")
        session.add(profile)
        session.commit()
        session.refresh(profile)
    return profile


def update_profile(session: Session, data: dict) -> UserProfile:
    profile = get_or_create_profile(session)
    for key in ("name", "phone", "email"):
        if key in data:
            setattr(profile, key, data[key])
    from datetime import datetime
    profile.updated_at = datetime.utcnow()
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


# ── Internships ─────────────────────────────────────────

def list_internships(session: Session, profile_id: int) -> list[Internship]:
    return list(session.exec(
        select(Internship).where(Internship.profile_id == profile_id)
    ).all())


def create_internship(session: Session, profile_id: int, data: dict) -> Internship:
    import json
    item = Internship(
        profile_id=profile_id,
        company=data.get("company", ""),
        position=data.get("position", ""),
        start_date=data.get("start_date", ""),
        end_date=data.get("end_date"),
        achievements=json.dumps(data.get("achievements", []), ensure_ascii=False),
    )
    session.add(item); session.commit(); session.refresh(item)
    return item


def update_internship(session: Session, item_id: int, data: dict) -> Optional[Internship]:
    import json
    item = session.get(Internship, item_id)
    if not item: return None
    for key in ("company", "position", "start_date", "end_date"):
        if key in data: setattr(item, key, data[key])
    if "achievements" in data:
        item.achievements = json.dumps(data["achievements"], ensure_ascii=False)
    session.add(item); session.commit(); session.refresh(item)
    return item


def delete_internship(session: Session, item_id: int) -> bool:
    item = session.get(Internship, item_id)
    if not item: return False
    session.delete(item); session.commit()
    return True


# ── Projects ────────────────────────────────────────────

def list_projects(session: Session, profile_id: int) -> list[Project]:
    return list(session.exec(
        select(Project).where(Project.profile_id == profile_id)
    ).all())


def create_project(session: Session, profile_id: int, data: dict) -> Project:
    import json
    item = Project(
        profile_id=profile_id,
        type=data.get("type", "project"),
        name=data.get("name", ""),
        role=data.get("role", ""),
        tech_stack=json.dumps(data.get("tech_stack", []), ensure_ascii=False),
        challenge=data.get("challenge", ""),
        solution=data.get("solution", ""),
        result=data.get("result", ""),
    )
    session.add(item); session.commit(); session.refresh(item)
    return item


def update_project(session: Session, item_id: int, data: dict) -> Optional[Project]:
    import json
    item = session.get(Project, item_id)
    if not item: return None
    for key in ("type", "name", "role", "challenge", "solution", "result"):
        if key in data: setattr(item, key, data[key])
    if "tech_stack" in data:
        item.tech_stack = json.dumps(data["tech_stack"], ensure_ascii=False)
    session.add(item); session.commit(); session.refresh(item)
    return item


def delete_project(session: Session, item_id: int) -> bool:
    item = session.get(Project, item_id)
    if not item: return False
    session.delete(item); session.commit()
    return True


# ── Skills ──────────────────────────────────────────────

def list_skills(session: Session, profile_id: int) -> list[Skill]:
    return list(session.exec(
        select(Skill).where(Skill.profile_id == profile_id)
    ).all())


def create_skill(session: Session, profile_id: int, data: dict) -> Skill:
    item = Skill(
        profile_id=profile_id,
        category=data.get("category", "language"),
        name=data.get("name", ""),
        proficiency=data.get("proficiency", "熟悉"),
    )
    session.add(item); session.commit(); session.refresh(item)
    return item


def update_skill(session: Session, item_id: int, data: dict) -> Optional[Skill]:
    item = session.get(Skill, item_id)
    if not item: return None
    for key in ("category", "name", "proficiency"):
        if key in data: setattr(item, key, data[key])
    session.add(item); session.commit(); session.refresh(item)
    return item


def delete_skill(session: Session, item_id: int) -> bool:
    item = session.get(Skill, item_id)
    if not item: return False
    session.delete(item); session.commit()
    return True
