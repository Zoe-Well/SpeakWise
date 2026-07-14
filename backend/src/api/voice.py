"""语音扩展配置 API"""

from fastapi import Body, APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.src.db.connection import get_session
from backend.src.services import profile_service
from backend.src.models.voice_adapter import VoiceAdapter

router = APIRouter(prefix="/api", tags=["voice"])


@router.get("/voice-adapters")
def list_adapters(session: Session = Depends(get_session)):
    profile = profile_service.get_or_create_profile(session)
    adapters = session.exec(select(VoiceAdapter).where(VoiceAdapter.profile_id == profile.id)).all()
    return [_va_out(a) for a in adapters]


@router.post("/voice-adapters")
def register_adapter(data: dict = Body(...), session: Session = Depends(get_session)):
    profile = profile_service.get_or_create_profile(session)
    va = VoiceAdapter(profile_id=profile.id, name=data["name"], adapter_type=data["adapter_type"],
                      enabled=data.get("enabled", False), settings=data.get("settings"))
    session.add(va); session.commit(); session.refresh(va)
    return _va_out(va)


@router.put("/voice-adapters/{adapter_id}")
def update_adapter(adapter_id: int, data: dict, session: Session = Depends(get_session)):
    va = session.get(VoiceAdapter, adapter_id)
    if not va: raise HTTPException(404)
    for key in ("name", "adapter_type", "enabled", "settings"):
        if key in data: setattr(va, key, data[key])
    session.add(va); session.commit(); session.refresh(va)
    return _va_out(va)


@router.delete("/voice-adapters/{adapter_id}")
def delete_adapter(adapter_id: int, session: Session = Depends(get_session)):
    va = session.get(VoiceAdapter, adapter_id)
    if not va: raise HTTPException(404)
    session.delete(va); session.commit()
    return {"ok": True}


@router.get("/voice-adapters/active")
def get_active_adapter(session: Session = Depends(get_session)):
    profile = profile_service.get_or_create_profile(session)
    va = session.exec(
        select(VoiceAdapter).where(VoiceAdapter.profile_id == profile.id, VoiceAdapter.enabled == True)
    ).first()
    if not va: raise HTTPException(404, detail="无启用的语音适配器")
    return _va_out(va)


def _va_out(va):
    return {"id": va.id, "name": va.name, "adapter_type": va.adapter_type,
            "enabled": va.enabled, "settings": va.settings}
