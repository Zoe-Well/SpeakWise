"""呈现偏好 + LLM 配置 API"""

import json as _json
from fastapi import Body, APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlmodel import Session, select
from openai import AsyncOpenAI

from backend.src.db.connection import get_session
from backend.src.services import profile_service
from backend.src.models.settings import DisplaySettings
from backend.src.models.apikey import ApiKey

router = APIRouter(prefix="/api", tags=["settings"])

# ── 支持的 LLM 厂商 ──
LLM_PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models_endpoint": "/models",
        "key_prefix": "sk-",
    },
    "openai": {
        "name": "OpenAI (GPT)",
        "base_url": "https://api.openai.com/v1",
        "models_endpoint": "/models",
        "key_prefix": "sk-",
    },
    "anthropic": {
        "name": "Anthropic (Claude)",
        "base_url": "https://api.anthropic.com/v1",
        "models_endpoint": "/models",
        "key_prefix": "sk-ant-",
    },
}

# ── 已知模型列表（/models 端点不是所有厂商都支持）──
_KNOWN_MODELS = {
    "deepseek": ["deepseek-v4-pro", "deepseek-chat", "deepseek-reasoner"],
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "o4-mini", "o3-mini"],
    "anthropic": ["claude-sonnet-4-20250514", "claude-haiku-3-5-20250514", "claude-opus-4-20250514"],
}


@router.post("/settings/llm/validate")
async def validate_llm_key(data: dict = Body(...)):
    """验证 API Key 并返回可用模型列表。body: { provider, api_key }"""
    provider_key = data.get("provider", "deepseek")
    api_key = data.get("api_key", "").strip()
    provider = LLM_PROVIDERS.get(provider_key)
    if not provider:
        raise HTTPException(400, f"不支持的厂商: {provider_key}")
    if not api_key:
        raise HTTPException(400, "API Key 不能为空")

    client = AsyncOpenAI(api_key=api_key, base_url=provider["base_url"], timeout=25.0)
    models = _KNOWN_MODELS.get(provider_key, [])

    # Validate key: try a minimal chat completion directly (faster than /models)
    key_valid = False
    try:
        test_model = models[0] if models else "deepseek-chat"
        await client.chat.completions.create(
            model=test_model, messages=[{"role": "user", "content": "hi"}],
            max_tokens=1, temperature=0, stream=False,
        )
        key_valid = True
    except Exception as e:
        msg = str(e).lower()
        if any(w in msg for w in ["401", "403", "unauthorized", "invalid", "incorrect", "authentication"]):
            raise HTTPException(401, "API Key 无效或没有权限")
        # Try with the other model name as fallback
        alt_model = models[1] if len(models) > 1 else None
        if alt_model:
            try:
                alt_client = AsyncOpenAI(api_key=api_key, base_url=provider["base_url"], timeout=25.0)
                await alt_client.chat.completions.create(
                    model=alt_model, messages=[{"role": "user", "content": "hi"}],
                    max_tokens=1, temperature=0, stream=False,
                )
                key_valid = True
            except Exception as e2:
                msg2 = str(e2).lower()
                if any(w in msg2 for w in ["401", "403", "unauthorized", "invalid", "incorrect", "authentication"]):
                    raise HTTPException(401, "API Key 无效或没有权限")
                raise HTTPException(400, f"验证失败: {e2}")
        if not key_valid:
            raise HTTPException(400, f"验证失败: {e}")

    if not key_valid:
        raise HTTPException(400, "无法验证 API Key，请检查网络连接")

    return {"valid": True, "models": models}


@router.get("/settings/llm")
def get_llm_settings(session: Session = Depends(get_session)):
    """获取当前 LLM 配置。"""
    profile = profile_service.get_or_create_profile(session)
    ds = session.exec(select(DisplaySettings).where(DisplaySettings.profile_id == profile.id)).first()
    if not ds:
        return {"provider": "deepseek", "api_key": "", "model": ""}
    return {
        "provider": ds.llm_provider or "deepseek",
        "api_key": ds.llm_api_key or "",
        "model": ds.llm_model or "",
        "data_dir": _get_data_dir(),
    }


@router.put("/settings/llm")
def update_llm_settings(data: dict = Body(...), session: Session = Depends(get_session)):
    """保存 LLM 配置。body: { provider, api_key, model }"""
    profile = profile_service.get_or_create_profile(session)
    ds = session.exec(select(DisplaySettings).where(DisplaySettings.profile_id == profile.id)).first()
    if not ds:
        ds = DisplaySettings(profile_id=profile.id)
        session.add(ds)
    field_map = {"provider": "llm_provider", "api_key": "llm_api_key", "model": "llm_model"}
    for json_field, db_field in field_map.items():
        if json_field in data:
            setattr(ds, db_field, data[json_field])
    session.add(ds); session.commit(); session.refresh(ds)
    return {"ok": True}


@router.get("/settings/data-dir")
def get_data_dir(session: Session = Depends(get_session)):
    """返回当前数据存储路径及概要。"""
    import os as _os
    data_dir = _os.environ.get("SPEAKWISE_DATA_DIR", "data/")
    abs_path = _os.path.abspath(data_dir)
    db_path = _os.path.join(abs_path, "copilot.db")

    # Count stored data
    from backend.src.models.session import Message, ConversationSession
    from backend.src.models.profile import Internship, Project, Skill, UserProfile
    from backend.src.models.job_context import JobContext
    from backend.src.models.document import SourceDocument
    from backend.src.models.template import PromptTemplate, TemplateDefault

    profile = profile_service.get_or_create_profile(session)
    summary = {
        "sessions": len(session.exec(select(ConversationSession).where(ConversationSession.profile_id == profile.id)).all()),
        "messages": len(session.exec(select(Message).where(Message.session_id.in_(
            session.exec(select(ConversationSession.id).where(ConversationSession.profile_id == profile.id)).all()
        ))).all()) if session.exec(select(ConversationSession.id).where(ConversationSession.profile_id == profile.id)).all() else 0,
        "skills": len(session.exec(select(Skill).where(Skill.profile_id == profile.id)).all()),
        "projects": len(session.exec(select(Project).where(Project.profile_id == profile.id)).all()),
        "internships": len(session.exec(select(Internship).where(Internship.profile_id == profile.id)).all()),
        "documents": len(session.exec(select(SourceDocument).where(SourceDocument.profile_id == profile.id)).all()),
        "templates": len(session.exec(select(PromptTemplate).where(PromptTemplate.profile_id == profile.id)).all()),
        "jd_contexts": len(session.exec(select(JobContext).where(JobContext.profile_id == profile.id)).all()),
        "db_size_kb": round(_os.path.getsize(db_path) / 1024, 1) if _os.path.exists(db_path) else 0,
    }
    return {"data_dir": abs_path, "db_file": db_path, "summary": summary}


# ── API Key 管理（多 Key 支持）──

@router.get("/settings/apikeys")
def list_apikeys(session: Session = Depends(get_session)):
    profile = profile_service.get_or_create_profile(session)
    rows = session.exec(select(ApiKey).where(ApiKey.profile_id == profile.id).order_by(ApiKey.created_at.desc())).all()
    return [{"id": r.id, "provider": r.provider, "name": r.name,
             "api_key": r.api_key[:8] + "..." if r.api_key else "",
             "model": r.model, "is_active": r.is_active,
             "created_at": r.created_at.isoformat()} for r in rows]


@router.post("/settings/apikeys")
def add_apikey(data: dict = Body(...), session: Session = Depends(get_session)):
    profile = profile_service.get_or_create_profile(session)
    k = ApiKey(profile_id=profile.id, provider=data.get("provider", "deepseek"),
               name=data.get("name", ""), api_key=data.get("api_key", ""),
               model=data.get("model", ""))
    session.add(k); session.commit(); session.refresh(k)
    return {"id": k.id, "name": k.name, "provider": k.provider, "model": k.model}


@router.put("/settings/apikeys/{key_id}")
def update_apikey(key_id: int, data: dict = Body(...), session: Session = Depends(get_session)):
    """更新 Key（model 字段）。"""
    profile = profile_service.get_or_create_profile(session)
    k = session.get(ApiKey, key_id)
    if not k or k.profile_id != profile.id:
        raise HTTPException(404)
    if "model" in data:
        k.model = data["model"]
    session.add(k); session.commit()
    return {"ok": True}


@router.put("/settings/apikeys/{key_id}/activate")
def activate_apikey(key_id: int, data: dict = Body(...), session: Session = Depends(get_session)):
    """激活 Key，同时保存 model。body: { model? }"""
    profile = profile_service.get_or_create_profile(session)
    for r in session.exec(select(ApiKey).where(ApiKey.profile_id == profile.id)).all():
        r.is_active = False; session.add(r)
    k = session.get(ApiKey, key_id)
    if not k or k.profile_id != profile.id:
        raise HTTPException(404)
    k.is_active = True
    if "model" in data:
        k.model = data["model"]
    session.add(k); session.commit()
    return {"ok": True}


@router.post("/settings/apikeys/{key_id}/validate")
async def validate_stored_key(key_id: int, session: Session = Depends(get_session)):
    """使用已存储的 Key 验证有效性并返回模型列表。"""
    profile = profile_service.get_or_create_profile(session)
    k = session.get(ApiKey, key_id)
    if not k or k.profile_id != profile.id:
        raise HTTPException(404)
    provider = LLM_PROVIDERS.get(k.provider)
    if not provider:
        raise HTTPException(400, f"不支持的厂商: {k.provider}")
    client = AsyncOpenAI(api_key=k.api_key, base_url=provider["base_url"], timeout=30.0)
    models = _KNOWN_MODELS.get(k.provider, [])
    try:
        # Try the cheapest model first to validate
        test_model = models[-1] if len(models) > 1 else models[0] if models else "deepseek-chat"
        await client.chat.completions.create(
            model=test_model, messages=[{"role": "user", "content": "hi"}],
            max_tokens=1, temperature=0, stream=False,
        )
        return {"valid": True, "models": _KNOWN_MODELS.get(k.provider, [])}
    except Exception as e:
        msg = str(e).lower()
        if any(w in msg for w in ["401","403","unauthorized","invalid","incorrect","authentication"]):
            raise HTTPException(401, "API Key 已失效")
        raise HTTPException(400, f"验证失败: {e}")


@router.delete("/settings/apikeys/{key_id}")
def delete_apikey(key_id: int, session: Session = Depends(get_session)):
    profile = profile_service.get_or_create_profile(session)
    k = session.get(ApiKey, key_id)
    if not k or k.profile_id != profile.id:
        raise HTTPException(404)
    session.delete(k); session.commit()
    return {"ok": True}


def get_active_apikey(db) -> dict | None:
    profile = profile_service.get_or_create_profile(db)
    k = db.exec(select(ApiKey).where(ApiKey.profile_id == profile.id, ApiKey.is_active == True)).first()
    if k:
        return {"provider": k.provider, "api_key": k.api_key, "model": k.model}
    return None


# ── 讯飞语音配置 ──

@router.get("/settings/voice")
def get_voice_settings(session: Session = Depends(get_session)):
    profile = profile_service.get_or_create_profile(session)
    ds = session.exec(select(DisplaySettings).where(DisplaySettings.profile_id == profile.id)).first()
    if not ds:
        return {"appid": "", "api_key": "", "api_secret": ""}
    return {"appid": ds.xf_appid or "", "api_key": ds.xf_api_key or "", "api_secret": ds.xf_api_secret or ""}

@router.put("/settings/voice")
def update_voice_settings(data: dict = Body(...), session: Session = Depends(get_session)):
    profile = profile_service.get_or_create_profile(session)
    ds = session.exec(select(DisplaySettings).where(DisplaySettings.profile_id == profile.id)).first()
    if not ds:
        ds = DisplaySettings(profile_id=profile.id); session.add(ds)
    field_map = {"appid": "xf_appid", "api_key": "xf_api_key", "api_secret": "xf_api_secret"}
    for json_f, db_f in field_map.items():
        if json_f in data: setattr(ds, db_f, data[json_f])
    session.add(ds); session.commit()
    return {"ok": True}

@router.post("/settings/voice/auth-url")
def get_xfyun_auth_url(data: dict = Body(...), session: Session = Depends(get_session)):
    """生成讯飞 WebSocket 认证 URL。"""
    import hashlib, hmac, base64
    from datetime import datetime, timezone

    profile = profile_service.get_or_create_profile(session)
    ds = session.exec(select(DisplaySettings).where(DisplaySettings.profile_id == profile.id)).first()
    api_key = data.get("api_key") or (ds.xf_api_key if ds else "")
    api_secret = data.get("api_secret") or (ds.xf_api_secret if ds else "")

    if not api_key or not api_secret:
        raise HTTPException(400, "请先配置讯飞 API Key 和 Secret")

    host = "iat-api.xfyun.cn"
    path = "/v2/iat"
    now = datetime.now(timezone.utc)
    date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    signature_sha = hmac.new(api_secret.encode(), signature_origin.encode(), hashlib.sha256).digest()
    signature = base64.b64encode(signature_sha).decode()
    authorization_origin = f'api_key="{api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'
    authorization = base64.b64encode(authorization_origin.encode()).decode()
    import urllib.parse
    appid = data.get("appid") or (ds.xf_appid if ds else "")
    url = f"wss://{host}{path}?authorization={urllib.parse.quote(authorization)}&date={urllib.parse.quote(date)}&host={host}"
    return {"url": url, "appid": appid}


# ── 语音转写（完整音频 → iFlytek WebSocket → 文字）──

@router.post("/voice/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    sample_rate: str = Form("16000"),
    session: Session = Depends(get_session),
):
    """接收 PCM 音频，通过讯飞 WebSocket 转写为文字。"""
    profile = profile_service.get_or_create_profile(session)
    ds = session.exec(select(DisplaySettings).where(DisplaySettings.profile_id == profile.id)).first()
    if not ds or not ds.xf_api_key or not ds.xf_api_secret:
        raise HTTPException(400, "请先配置讯飞语音服务")

    raw = await audio.read()
    if len(raw) == 0:
        return {"text": ""}

    # Generate auth URL
    import hashlib, hmac, base64, urllib.parse
    from datetime import datetime, timezone
    host = "iat-api.xfyun.cn"; path = "/v2/iat"
    now = datetime.now(timezone.utc)
    date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
    sig_input = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    sig_sha = hmac.new(ds.xf_api_secret.encode(), sig_input.encode(), hashlib.sha256).digest()
    sig_b64 = base64.b64encode(sig_sha).decode()
    auth_raw = f'api_key="{ds.xf_api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{sig_b64}"'
    auth_b64 = base64.b64encode(auth_raw.encode()).decode()
    ws_url = f"wss://{host}{path}?authorization={urllib.parse.quote(auth_b64)}&date={urllib.parse.quote(date)}&host={host}"

    import asyncio, websockets, json as _json
    appid = ds.xf_appid or ""

    async def _do_transcribe():
        try:
            async with websockets.connect(ws_url, ping_interval=None, close_timeout=5) as w:
                await w.send(_json.dumps({
                    "common": {"app_id": appid},
                    "business": {"language": "zh_cn", "domain": "iat", "accent": "mandarin"},
                    "data": {"status": 0, "format": "audio/L16;rate=" + sample_rate, "encoding": "raw"}
                }))
                resp = await asyncio.wait_for(w.recv(), timeout=5)
                # Send PCM audio
                await w.send(raw)
                await w.send(_json.dumps({"data": {"status": 2}}))
                # Collect results
                full_text = ""
                while True:
                    try:
                        resp = await asyncio.wait_for(w.recv(), timeout=5)
                        msg = _json.loads(resp)
                        if msg.get("code", 0) != 0:
                            break
                        if msg.get("data", {}).get("result"):
                            for ws1 in msg["data"]["result"].get("ws", []):
                                for cw in ws1.get("cw", []):
                                    full_text += cw.get("w", "")
                        if msg.get("data", {}).get("status") == 2:
                            break
                    except asyncio.TimeoutError:
                        break
                return full_text
        except Exception:
            return ""

    text = await _do_transcribe()
    return {"text": text}


def _get_data_dir() -> str:
    """获取数据目录路径。"""
    import os as _os
    return _os.environ.get("SPEAKWISE_DATA_DIR", "data/")


@router.get("/settings/display")
def get_display_settings(session: Session = Depends(get_session)):
    profile = profile_service.get_or_create_profile(session)
    ds = session.exec(select(DisplaySettings).where(DisplaySettings.profile_id == profile.id)).first()
    if not ds:
        ds = DisplaySettings(profile_id=profile.id)
        session.add(ds); session.commit(); session.refresh(ds)
    return _ds_out(ds)


@router.put("/settings/display")
def update_display_settings(data: dict = Body(...), session: Session = Depends(get_session)):
    profile = profile_service.get_or_create_profile(session)
    ds = session.exec(select(DisplaySettings).where(DisplaySettings.profile_id == profile.id)).first()
    if not ds:
        ds = DisplaySettings(profile_id=profile.id)
        session.add(ds)
    for key in ("mode", "opacity", "position_x", "position_y", "stream_speed", "auto_scroll", "scroll_speed"):
        if key in data:
            setattr(ds, key, data[key])
    # Clamp opacity
    ds.opacity = max(0.35, min(1.0, ds.opacity or 0.95))
    session.add(ds); session.commit(); session.refresh(ds)
    return _ds_out(ds)


def _ds_out(ds):
    return {"mode": ds.mode, "opacity": ds.opacity, "position_x": ds.position_x,
            "position_y": ds.position_y, "stream_speed": ds.stream_speed,
            "auto_scroll": ds.auto_scroll, "scroll_speed": ds.scroll_speed}
