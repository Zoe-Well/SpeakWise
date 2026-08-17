"""知识库服务层：Profile / Internship / Project / Skill CRUD + 多简历管理"""

from typing import Optional
from sqlmodel import Session, select, delete
from backend.src.models.profile import UserProfile, Internship, Project, Skill


# ── Profile (Resume) Management ───────────────────────────

def get_or_create_profile(session: Session) -> UserProfile:
    """获取第一个 UserProfile，若不存在则创建默认档案。（向后兼容）"""
    profile = session.exec(select(UserProfile)).first()
    if not profile:
        profile = UserProfile(name="未命名")
        session.add(profile)
        session.commit()
        session.refresh(profile)
    return profile


def get_active_profile(session: Session) -> UserProfile:
    """获取当前激活的简历（is_active=True），若无则激活第一条。"""
    profile = session.exec(
        select(UserProfile).where(UserProfile.is_active == True)  # noqa: E712
    ).first()
    if not profile:
        profile = get_or_create_profile(session)
        profile.is_active = True
        session.add(profile)
        session.commit()
        session.refresh(profile)
    return profile


def list_profiles(session: Session) -> list[dict]:
    """列出所有简历，附带统计信息。"""
    profiles = session.exec(select(UserProfile).order_by(UserProfile.updated_at.desc())).all()
    result = []
    for p in profiles:
        internships_n = len(list_internships(session, p.id))
        projects_n = len(list_projects(session, p.id))
        skills_n = len(list_skills(session, p.id))
        result.append({
            "id": p.id, "name": p.name, "phone": p.phone, "email": p.email,
            "is_active": p.is_active, "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            "internship_count": internships_n, "project_count": projects_n, "skill_count": skills_n,
        })
    return result


def create_profile(session: Session, data: dict) -> UserProfile:
    """创建新简历并自动激活（取消其他简历的激活状态）。"""
    profile = UserProfile(
        name=data.get("name", "新简历"),
        phone=data.get("phone"),
        email=data.get("email"),
        is_active=True,
    )
    session.add(profile)
    session.flush()  # 获取新 profile 的 id，用于排除它
    # 取消其他所有简历的激活状态
    for p in session.exec(select(UserProfile).where(UserProfile.id != profile.id)).all():
        p.is_active = False
        session.add(p)
    session.commit()
    session.refresh(profile)
    return profile


def update_profile(session: Session, data: dict, profile_id: int | None = None) -> UserProfile:
    """更新简历基本信息。若未指定 profile_id，更新活跃简历。"""
    if profile_id:
        profile = session.get(UserProfile, profile_id)
        if not profile:
            raise ValueError(f"Profile {profile_id} not found")
    else:
        profile = get_active_profile(session)
    for key in ("name", "phone", "email"):
        if key in data:
            setattr(profile, key, data[key])
    from datetime import datetime
    profile.updated_at = datetime.utcnow()
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def activate_profile(session: Session, profile_id: int) -> UserProfile:
    """激活指定简历，同时取消其他简历的激活状态。"""
    # Deactivate all
    all_profiles = session.exec(select(UserProfile)).all()
    for p in all_profiles:
        p.is_active = (p.id == profile_id)
        session.add(p)
    session.commit()
    profile = session.get(UserProfile, profile_id)
    if not profile:
        raise ValueError(f"Profile {profile_id} not found")
    return profile


def delete_profile(session: Session, profile_id: int) -> bool:
    """删除简历，级联删除其关联数据。禁止删除最后一个。"""
    all_profiles = session.exec(select(UserProfile)).all()
    if len(all_profiles) <= 1:
        raise ValueError("Cannot delete the last resume")
    profile = session.get(UserProfile, profile_id)
    if not profile:
        return False

    # Cascade delete related data
    for model in [Internship, Project, Skill]:
        session.exec(delete(model).where(model.profile_id == profile_id))  # type: ignore[arg-type]
    # Delete related documents
    from backend.src.models.document import SourceDocument, ProfileUpdateProposal
    session.exec(delete(SourceDocument).where(SourceDocument.profile_id == profile_id))  # type: ignore[arg-type]
    # Delete related proposals
    session.exec(delete(ProfileUpdateProposal).where(ProfileUpdateProposal.profile_id == profile_id))  # type: ignore[arg-type]
    # Delete related job contexts
    from backend.src.models.job_context import JobContext
    session.exec(delete(JobContext).where(JobContext.profile_id == profile_id))  # type: ignore[arg-type]

    was_active = profile.is_active
    session.delete(profile)
    session.commit()

    # If the deleted profile was active, activate the first remaining
    if was_active:
        first = session.exec(select(UserProfile)).first()
        if first:
            first.is_active = True
            session.add(first)
            session.commit()

    return True


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


def apply_skill_categories(session: Session, profile_id: int, assignments: list[dict]) -> list[Skill]:
    """Atomically apply normalized categories to skills owned by one profile."""
    from backend.src.services.skill_categorizer import normalize_category

    assignment_ids = [assignment["id"] for assignment in assignments]
    if len(assignment_ids) != len(set(assignment_ids)):
        raise ValueError("技能分类不能重复")

    skills = list(session.exec(select(Skill).where(Skill.id.in_(assignment_ids))).all())
    skills_by_id = {skill.id: skill for skill in skills}
    if any(skill_id not in skills_by_id or skills_by_id[skill_id].profile_id != profile_id for skill_id in assignment_ids):
        raise ValueError("技能必须属于当前活跃简历")

    for assignment in assignments:
        skill = skills_by_id[assignment["id"]]
        skill.category = normalize_category(assignment["category"])
        session.add(skill)
    session.commit()

    updated = []
    for assignment in assignments:
        skill = skills_by_id[assignment["id"]]
        session.refresh(skill)
        updated.append(skill)
    return updated
