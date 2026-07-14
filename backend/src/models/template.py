"""提示词模板模型：PromptTemplate + TemplateDefault"""

from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class PromptTemplate(SQLModel, table=True):
    __tablename__ = "prompt_templates"

    id: str = Field(primary_key=True, max_length=100)  # user-defined ID prefix (bt1, ct1700...)
    profile_id: int
    scope: str = Field(max_length=30)  # self_intro | scenario | technical
    name: str = Field(max_length=200)
    structure_rules: Optional[str] = Field(default=None, max_length=4000)  # JSON
    style_rules: Optional[str] = Field(default=None, max_length=2000)  # JSON
    is_builtin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TemplateDefault(SQLModel, table=True):
    """每个 scope 的默认模板选择。一个 profile+scope 最多一条记录。"""
    __tablename__ = "template_defaults"

    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int
    scope: str = Field(max_length=30)  # self_intro | scenario | technical
    template_id: str = Field(max_length=100)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
