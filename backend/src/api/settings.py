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
    "deepseek": ["deepseek-v4-pro", "deepseek-v4-flash"],
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "o4-mini", "o3-mini"],
    "anthropic": ["claude-sonnet-4-20250514", "claude-haiku-3-5-20250514", "claude-opus-4-20250514"],
}


def _provider_error_status(exc: Exception) -> int | None:
    """Return the upstream HTTP status without parsing provider error text."""
    status = getattr(exc, "status_code", None)
    return status if isinstance(status, int) else None


def _raise_validation_error(exc: Exception) -> None:
    """Map provider failures to stable, non-sensitive API errors."""
    status = _provider_error_status(exc)
    if status in (401, 403):
        raise HTTPException(401, "API Key 无效或没有访问权限")
    if status == 402:
        raise HTTPException(402, "API Key 余额不足")
    if status == 429:
        raise HTTPException(429, "模型服务请求过于频繁，请稍后重试")
    raise HTTPException(400, "API Key 验证失败，请检查模型权限或网络连接")


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

    # Validate key by trying each model in sequence (first success → valid)
    last_error: Exception | None = None
    for model_name in models:
        try:
            await client.chat.completions.create(
                model=model_name, messages=[{"role": "user", "content": "hi"}],
                max_tokens=1, temperature=0, stream=False,
            )
            return {"valid": True, "models": models}
        except Exception as e:
            last_error = e
            if _provider_error_status(e) in (401, 402, 403, 429):
                _raise_validation_error(e)

    # All models failed
    if last_error is not None:
        _raise_validation_error(last_error)
    raise HTTPException(400, "没有可用于验证的模型")


@router.get("/settings/llm")
def get_llm_settings(session: Session = Depends(get_session)):
    """获取当前 LLM 配置（统一通过 get_active_apikey，兼容多 Key 系统和旧 DisplaySettings）。"""
    key_info = get_active_apikey(session)
    return {
        "provider": key_info["provider"] if key_info else "deepseek",
        "api_key": key_info["api_key"] if key_info else "",
        "model": key_info.get("model", "") if key_info else "",
        "data_dir": _get_data_dir(),
    }


@router.get("/settings/llm/status")
def get_llm_status(session: Session = Depends(get_session)):
    """检查 LLM 是否已配置（快速检查，不实际调用 LLM）。"""
    key_info = get_active_apikey(session)
    if key_info and key_info.get("api_key"):
        return {"configured": True, "provider": key_info.get("provider", "")}
    return {"configured": False, "provider": ""}


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

async def _validate_key(provider_key: str, api_key: str) -> None:
    """验证 API Key 有效性。无效时抛出 HTTPException。"""
    provider = LLM_PROVIDERS.get(provider_key)
    if not provider:
        raise HTTPException(400, f"不支持的厂商: {provider_key}")
    client = AsyncOpenAI(api_key=api_key, base_url=provider["base_url"], timeout=25.0)
    models = _KNOWN_MODELS.get(provider_key, [])
    last_error: Exception | None = None
    for model_name in models:
        try:
            await client.chat.completions.create(
                model=model_name, messages=[{"role": "user", "content": "hi"}],
                max_tokens=1, temperature=0, stream=False,
            )
            return
        except Exception as e:
            last_error = e
            if _provider_error_status(e) in (401, 402, 403, 429):
                _raise_validation_error(e)

    if last_error is not None:
        _raise_validation_error(last_error)
    raise HTTPException(400, "当前服务商没有可用于验证的模型")


@router.get("/settings/apikeys")
def list_apikeys(session: Session = Depends(get_session)):
    rows = session.exec(select(ApiKey).order_by(ApiKey.created_at.desc())).all()
    return [{"id": r.id, "provider": r.provider, "name": r.name,
             "api_key": r.api_key[:8] + "..." if r.api_key else "",
             "model": r.model, "is_active": r.is_active,
             "created_at": r.created_at.isoformat()} for r in rows]


@router.post("/settings/apikeys")
async def add_apikey(data: dict = Body(...), session: Session = Depends(get_session)):
    """添加 API Key（去重 + 验证 + 首个 Key 自动激活）。"""
    provider_key = data.get("provider", "deepseek")
    api_key = data.get("api_key", "").strip()
    if not api_key:
        raise HTTPException(400, "API Key 不能为空")

    # 1. 去重：Key 值
    if session.exec(select(ApiKey).where(ApiKey.api_key == api_key)).first():
        raise HTTPException(409, "该 API Key 已存在，无需重复添加")
    # 2. 去重：名称
    name = data.get("name", "").strip()
    if name and session.exec(select(ApiKey).where(ApiKey.name == name)).first():
        raise HTTPException(409, f"名称「{name}」已被使用，请更换名称")

    # 2. 验证有效性
    await _validate_key(provider_key, api_key)

    # 3. 如果是第一个 Key，自动激活
    is_first = session.exec(select(ApiKey)).first() is None

    k = ApiKey(profile_id=0, provider=provider_key,
               name=name, api_key=api_key,
               model=data.get("model", ""), is_active=is_first)
    session.add(k); session.commit(); session.refresh(k)
    return {"id": k.id, "name": k.name, "provider": k.provider, "model": k.model, "is_active": k.is_active}


@router.put("/settings/apikeys/{key_id}")
def update_apikey(key_id: int, data: dict = Body(...), session: Session = Depends(get_session)):
    """更新 Key（model 字段）。"""
    k = session.get(ApiKey, key_id)
    if not k:
        raise HTTPException(404)
    if "model" in data:
        k.model = data["model"]
    session.add(k); session.commit()
    return {"ok": True}


@router.put("/settings/apikeys/{key_id}/activate")
async def activate_apikey(key_id: int, data: dict = Body(...), session: Session = Depends(get_session)):
    """激活 Key（先验证有效性）。body: { model? }"""
    k = session.get(ApiKey, key_id)
    if not k:
        raise HTTPException(404)

    # 验证 Key 仍然有效
    await _validate_key(k.provider, k.api_key)

    # 全量 deactivate
    for r in session.exec(select(ApiKey)).all():
        r.is_active = False; session.add(r)
    # 激活目标
    k.is_active = True
    if "model" in data:
        k.model = data["model"]
    session.add(k); session.commit()
    return {"ok": True}


@router.post("/settings/apikeys/{key_id}/validate")
async def validate_stored_key(key_id: int, session: Session = Depends(get_session)):
    """使用已存储的 Key 验证有效性并返回模型列表。"""
    k = session.get(ApiKey, key_id)
    if not k:
        raise HTTPException(404)
    await _validate_key(k.provider, k.api_key)
    return {"valid": True, "models": _KNOWN_MODELS.get(k.provider, [])}


@router.delete("/settings/apikeys/{key_id}")
def delete_apikey(key_id: int, session: Session = Depends(get_session)):
    k = session.get(ApiKey, key_id)
    if not k:
        raise HTTPException(404)
    session.delete(k); session.commit()
    return {"ok": True}


def get_active_apikey(db) -> dict | None:
    """获取当前活跃的 API Key（全局，不绑定 profile）。优先 ApiKey 表，回退到 DisplaySettings。"""
    from backend.src.models.settings import DisplaySettings
    # Priority 1: ApiKey table (multi-key system, global)
    active_keys = db.exec(select(ApiKey).where(ApiKey.is_active == True)).all()
    # 修复历史遗留的多个 active：只保留第一个
    if len(active_keys) > 1:
        for k in active_keys[1:]:
            k.is_active = False
            db.add(k)
        db.commit()
    if active_keys and active_keys[0].api_key:
        return {"provider": active_keys[0].provider, "api_key": active_keys[0].api_key, "model": active_keys[0].model}
    # Priority 2: DisplaySettings (legacy single-key, global)
    ds = db.exec(select(DisplaySettings)).first()
    if ds and ds.llm_api_key:
        return {"provider": ds.llm_provider or "deepseek", "api_key": ds.llm_api_key, "model": ds.llm_model or ""}
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
