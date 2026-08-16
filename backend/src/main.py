"""SpeakWise 后端入口 — FastAPI 应用"""

import base64
import hmac
import sys, os
# PyInstaller 兼容: standalone exe 运行时把 backend/src 的父目录加入 path
_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _path not in sys.path:
    sys.path.insert(0, _path)

# 仅开发环境从 .env 加载；PyInstaller 打包后通过 SPEAKWISE_DATA_DIR 中的配置获取
import sys as _sys
if not getattr(_sys, "frozen", False):  # PyInstaller sets sys.frozen = True
    from dotenv import load_dotenv
    load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.src.db.connection import init_db
from backend.src.api.profile import router as profile_router
from backend.src.api.sessions import router as sessions_router
from backend.src.api.generate import router as generate_router
from backend.src.api.templates import router as templates_router
from backend.src.api.documents import router as documents_router
from backend.src.api.settings import router as settings_router
from backend.src.api.voice import router as voice_router
from backend.src.api.jd import router as jd_router
from backend.src.api.review import router as review_router
from backend.src.api.interview import router as interview_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库，关闭时清理连接。"""
    init_db()
    yield


app = FastAPI(
    title="SpeakWise",
    description="智能面试助手（Interview Copilot）后端服务",
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def optional_basic_auth(request, call_next):
    """Protect the single-user web demo when Railway auth variables are set."""
    username = os.environ.get("APP_BASIC_AUTH_USER", "")
    password = os.environ.get("APP_BASIC_AUTH_PASSWORD", "")
    if not username or not password or request.url.path == "/api/health":
        return await call_next(request)

    supplied = request.headers.get("Authorization", "")
    expected = "Basic " + base64.b64encode(
        f"{username}:{password}".encode("utf-8")
    ).decode("ascii")
    if not hmac.compare_digest(supplied, expected):
        return PlainTextResponse(
            "Authentication required",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="SpeakWise"'},
        )
    return await call_next(request)

# CORS — 仅允许前端开发服务器和桌面应用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "app://."],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)


app.include_router(profile_router)
app.include_router(sessions_router)
app.include_router(generate_router)
app.include_router(templates_router)
app.include_router(documents_router)
app.include_router(settings_router)
app.include_router(voice_router)
app.include_router(jd_router)
app.include_router(review_router)
app.include_router(interview_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


# Railway serves the built Vite application and API from the same origin.
_frontend_dist = os.environ.get("FRONTEND_DIST_DIR") or os.path.join(
    _path, "frontend", "dist"
)
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")


if __name__ == "__main__":
    import sys, os, argparse
    import uvicorn
    # Support running directly (PyInstaller) — add parent to path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
