"""会话与消息模型：ConversationSession, Message"""

from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class ConversationSession(SQLModel, table=True):
    __tablename__ = "conversation_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int
    name: str = Field(max_length=200)
    mode: str = Field(default="interview", max_length=20)  # "normal" | "interview" | "mock"
    jd_context_id: Optional[int] = Field(default=None, nullable=True)
    active_template_id: Optional[str] = Field(default=None, max_length=100)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="conversation_sessions.id")
    role: str = Field(max_length=20)  # user | assistant
    command: Optional[str] = Field(default=None, max_length=50)  # /intro | /scenario | /followup | null
    content: str = Field(default="")
    thinking: Optional[str] = Field(default=None, nullable=True)  # 模型思考链（仅在流式期间展示）
    type: str = Field(max_length=30)  # self_intro | scenario | follow_up | free_text | system
    response_id: Optional[int] = Field(default=None, nullable=True)
    source_experience_ids: Optional[str] = Field(default=None, max_length=500)  # JSON array
    created_at: datetime = Field(default_factory=datetime.utcnow)
