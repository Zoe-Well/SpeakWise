"""提示词模板 API"""

from fastapi import Body, APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.src.db.connection import get_session
from backend.src.services import profile_service
from backend.src.models.template import PromptTemplate, TemplateDefault

router = APIRouter(prefix="/api", tags=["templates"])

# Built-in seed
BUILTIN_TEMPLATES = [
    {"id": "bt_self_intro_default", "scope": "self_intro", "name": "默认自我介绍三段式", "is_builtin": True,
     "structure_rules": '{"sections":["概述","技能+证据","业务匹配"],"length":"300-400"}',
     "style_rules": '{"tone":"专业自然","fallback_angle":"学习角度"}'},
    {"id": "bt_scenario_default", "scope": "scenario", "name": "默认 STAR 分步骤", "is_builtin": True,
     "structure_rules": '{"framework":"STAR","step_min":3,"step_labels":["止损","排查","修复","复盘"]}',
     "style_rules": '{"tone":"沉稳克制","adapt_tone":true}'},
    {"id": "bt_technical_default", "scope": "technical", "name": "默认技术题五步法", "is_builtin": True,
     "structure_rules": '{"sections":["理解题意","思路分析","代码实现","测试用例","面试追问"],"code_required":true}',
     "style_rules": '{"tone":"专业清晰","include_complexity":true,"test_cases":2}'},
]


def _seed_builtins(session: Session):
    """确保内置模板存在（全局，profile_id=0）。"""
    for bt in BUILTIN_TEMPLATES:
        existing = session.get(PromptTemplate, bt["id"])
        if existing:
            # 修复孤儿数据：如果 profile_id 不是 0，更新为 0
            if existing.profile_id != 0:
                existing.profile_id = 0
                session.add(existing)
        else:
            session.add(PromptTemplate(profile_id=0, **bt))
    session.commit()


@router.get("/prompt-templates")
def list_templates(scope: str = None, session: Session = Depends(get_session)):
    _seed_builtins(session)
    stmt = select(PromptTemplate)
    if scope: stmt = stmt.where(PromptTemplate.scope == scope)
    return [_tpl_out(t) for t in session.exec(stmt).all()]


@router.post("/prompt-templates")
def create_template(data: dict = Body(...), session: Session = Depends(get_session)):
    tid = f"ct_{int(__import__('time').time() * 1000)}"
    structure = _validate_template_rules(data.get("structure_rules"), "structure_rules")
    style = _validate_template_rules(data.get("style_rules"), "style_rules")
    t = PromptTemplate(profile_id=0, id=tid, scope=data.get("scope", "self_intro"),
                       name=data.get("name", "新模板"), is_builtin=False,
                       structure_rules=structure, style_rules=style)
    session.add(t); session.commit(); session.refresh(t)
    return _tpl_out(t)


@router.put("/prompt-templates/defaults")
def set_template_default(data: dict = Body(...), session: Session = Depends(get_session)):
    """设置某个 scope 的默认模板。body: { scope, template_id }"""
    profile = profile_service.get_active_profile(session)
    scope = data.get("scope")
    tid = data.get("template_id")
    if not scope or not tid:
        raise HTTPException(400, "scope 和 template_id 为必填")
    tpl = session.get(PromptTemplate, tid)
    if not tpl:
        raise HTTPException(404, "模板不存在")
    existing = session.exec(
        select(TemplateDefault).where(
            TemplateDefault.profile_id == profile.id,
            TemplateDefault.scope == scope,
        )
    ).first()
    if existing:
        existing.template_id = tid
        session.add(existing)
    else:
        session.add(TemplateDefault(profile_id=profile.id, scope=scope, template_id=tid))
    session.commit()
    return {"ok": True}


@router.put("/prompt-templates/{template_id}")
def update_template(template_id: str, data: dict, session: Session = Depends(get_session)):
    t = session.get(PromptTemplate, template_id)
    if not t: raise HTTPException(404)
    if t.is_builtin:
        # Copy-on-edit
        import time
        new_id = f"ct_{int(time.time() * 1000)}"
        new_t = PromptTemplate(profile_id=0, id=new_id, scope=t.scope,
                               name=f"{t.name} (副本)", is_builtin=False,
                               structure_rules=data.get("structure_rules", t.structure_rules),
                               style_rules=data.get("style_rules", t.style_rules))
        session.add(new_t); session.commit(); session.refresh(new_t)
        return _tpl_out(new_t)
    for key in ("name", "structure_rules", "style_rules"):
        if key in data: setattr(t, key, data[key])
    session.add(t); session.commit(); session.refresh(t)
    return _tpl_out(t)


@router.delete("/prompt-templates/{template_id}")
def delete_template(template_id: str, session: Session = Depends(get_session)):
    t = session.get(PromptTemplate, template_id)
    if not t: raise HTTPException(404)
    if t.is_builtin: raise HTTPException(403, detail="内置模板不可删除")
    session.delete(t); session.commit()
    return {"ok": True}


def _validate_template_rules(value: str | None, field_name: str) -> str | None:
    """校验模板规则：必须为有效 JSON 或 None/空字符串。"""
    if value is None or value.strip() == "":
        return value
    import json as _json
    try:
        parsed = _json.loads(value)
        if not isinstance(parsed, dict):
            raise HTTPException(400, f"{field_name} 必须是 JSON 对象")
        # Limit string values + block prompt injection patterns
        _INJECTION_PATTERNS = ["ignore all previous", "ignore previous instructions",
                               "disregard", "system prompt:", "you are now",
                               "new instructions:", "override"]
        for k, v in parsed.items():
            if isinstance(v, str):
                if len(v) > 500:
                    raise HTTPException(400, f"{field_name}.{k} 值过长，最大 500 字符")
                v_lower = v.lower()
                for pat in _INJECTION_PATTERNS:
                    if pat in v_lower:
                        raise HTTPException(400, f"{field_name}.{k} 包含不允许的内容")
        return _json.dumps(parsed, ensure_ascii=False)
    except (_json.JSONDecodeError, ValueError) as e:
        raise HTTPException(400, f"{field_name} JSON 格式无效: {e}")


@router.post("/prompt-templates/import")
def import_template(data: dict = Body(...), session: Session = Depends(get_session)):
    import time
    tid = f"imp_{int(time.time() * 1000)}"
    structure = _validate_template_rules(data.get("structure_rules"), "structure_rules")
    style = _validate_template_rules(data.get("style_rules"), "style_rules")
    t = PromptTemplate(profile_id=0, id=tid, is_builtin=False,
                       scope=data.get("scope", "self_intro"), name=data.get("name", "导入模板"),
                       structure_rules=structure, style_rules=style)
    session.add(t); session.commit(); session.refresh(t)
    return _tpl_out(t)


def _tpl_out(t):
    return {"id": t.id, "scope": t.scope, "name": t.name, "is_builtin": t.is_builtin,
            "structure_rules": t.structure_rules, "style_rules": t.style_rules}


# ── Template defaults (per-scope active template) ──

@router.get("/prompt-templates/defaults")
def get_template_defaults(session: Session = Depends(get_session)):
    """获取每个 scope 的默认模板 ID。"""
    profile = profile_service.get_active_profile(session)
    rows = session.exec(
        select(TemplateDefault).where(TemplateDefault.profile_id == profile.id)
    ).all()
    return {r.scope: r.template_id for r in rows}
