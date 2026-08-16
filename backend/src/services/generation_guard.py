"""所有 LLM 生成入口共用的归属校验、并发锁与频率限制。"""

import time
from collections.abc import Callable

from fastapi import HTTPException
from sqlmodel import Session

from backend.src.models.session import ConversationSession


class GenerationGuard:
    def __init__(
        self,
        max_requests: int = 10,
        window_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.clock = clock
        self._active: set[str] = set()
        self._requests: dict[str, list[float]] = {}

    def try_acquire(self, key: str) -> str | None:
        now = self.clock()
        window = [
            timestamp
            for timestamp in self._requests.get(key, [])
            if now - timestamp < self.window_seconds
        ]
        if len(window) >= self.max_requests:
            self._requests[key] = window
            return "请求过于频繁，请稍后再试"
        if key in self._active:
            return "上一个请求尚未完成，请稍后"
        window.append(now)
        self._requests[key] = window
        self._active.add(key)
        return None

    def release(self, key: str) -> None:
        self._active.discard(key)


generation_guard = GenerationGuard()


def validate_owned_session(
    db: Session,
    session_id: int,
    profile_id: int,
    *,
    required_mode: str | None = None,
) -> ConversationSession:
    conversation = db.get(ConversationSession, session_id)
    if not conversation or conversation.profile_id != profile_id:
        raise HTTPException(404, "会话不存在")
    if required_mode and conversation.mode != required_mode:
        raise HTTPException(400, "会话模式不匹配")
    return conversation


def public_generation_error(exc: Exception) -> str:
    """生成接口统一错误脱敏；详细堆栈由调用方写日志。"""
    if isinstance(exc, HTTPException) and isinstance(exc.detail, str):
        return exc.detail
    return "生成失败，请重试"
