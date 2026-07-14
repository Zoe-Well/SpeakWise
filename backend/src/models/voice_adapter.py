"""语音扩展模型：VoiceAdapter"""

from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class VoiceAdapter(SQLModel, table=True):
    __tablename__ = "voice_adapters"

    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int
    name: str = Field(max_length=200)
    adapter_type: str = Field(max_length=100)
    enabled: bool = Field(default=False)
    settings: Optional[str] = Field(default=None, max_length=2000)  # JSON blob
    created_at: datetime = Field(default_factory=datetime.utcnow)
