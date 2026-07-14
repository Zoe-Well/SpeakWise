"""API Key 管理模型"""

from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class ApiKey(SQLModel, table=True):
    __tablename__ = "api_keys"

    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int
    provider: str = Field(default="deepseek", max_length=30)
    name: str = Field(default="", max_length=100)
    api_key: str = Field(default="", max_length=200)
    model: str = Field(default="", max_length=100)  # 该 Key 绑定的模型
    is_active: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
