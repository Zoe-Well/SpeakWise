"""文档与更新建议模型：SourceDocument, ProfileUpdateProposal"""

from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class SourceDocument(SQLModel, table=True):
    __tablename__ = "source_documents"

    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int
    scope: str = Field(max_length=20)  # profile | jd
    usage: str = Field(max_length=20)  # parse | attach
    filename: str = Field(max_length=300)
    file_type: str = Field(max_length=20)  # txt | docx | doc | pdf
    extracted_text: Optional[str] = Field(default=None, max_length=50000)
    parse_status: str = Field(default="pending", max_length=20)  # pending | success | failed
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProfileUpdateProposal(SQLModel, table=True):
    __tablename__ = "profile_update_proposals"

    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int
    document_id: int = Field(foreign_key="source_documents.id")
    changes: str = Field(default="[]", max_length=10000)  # JSON
    status: str = Field(default="pending", max_length=20)  # pending | confirmed | rejected
    clear_existing: bool = Field(default=False)  # 确认时是否先清空现有实习/项目/技能
    created_at: datetime = Field(default_factory=datetime.utcnow)
