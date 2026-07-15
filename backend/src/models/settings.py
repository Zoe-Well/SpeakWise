"""呈现偏好模型：DisplaySettings"""

from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class DisplaySettings(SQLModel, table=True):
    __tablename__ = "display_settings"

    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int
    mode: str = Field(default="inline", max_length=20)  # inline | floating
    opacity: float = Field(default=0.95)
    position_x: Optional[int] = Field(default=None, nullable=True)
    position_y: Optional[int] = Field(default=None, nullable=True)
    stream_speed: str = Field(default="normal", max_length=20)  # slow | normal | fast
    auto_scroll: bool = Field(default=True)
    scroll_speed: str = Field(default="normal", max_length=20)
    # LLM 配置
    llm_provider: Optional[str] = Field(default="deepseek", max_length=30)
    llm_api_key: Optional[str] = Field(default=None, max_length=200)
    llm_model: Optional[str] = Field(default=None, max_length=100)
    # 讯飞语音配置
    xf_appid: Optional[str] = Field(default=None, max_length=100)
    xf_api_key: Optional[str] = Field(default=None, max_length=200)
    xf_api_secret: Optional[str] = Field(default=None, max_length=200)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
