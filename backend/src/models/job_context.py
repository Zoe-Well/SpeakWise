"""岗位上下文模型"""

import json
from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class JobContext(SQLModel, table=True):
    __tablename__ = "job_contexts"

    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int
    name: str = Field(default="", max_length=200)
    raw_text: str = Field(default="")
    core_skills: str = Field(default="[]")  # JSON array
    duties: str = Field(default="[]")       # JSON array
    culture_values: str = Field(default="[]")  # JSON array
    is_active: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def to_analysis_dict(self) -> dict:
        """反序列化为 prompt 可直接使用的 dict。"""
        return {
            "core_skills": json.loads(self.core_skills) if self.core_skills else [],
            "duties": json.loads(self.duties) if self.duties else [],
            "culture_values": json.loads(self.culture_values) if self.culture_values else [],
        }

    @classmethod
    def from_analysis(cls, profile_id: int, raw_text: str, analysis: dict) -> "JobContext":
        """从 JD 分析结果构建模型实例。"""
        return cls(
            profile_id=profile_id,
            raw_text=raw_text,
            core_skills=json.dumps(analysis.get("core_skills", []), ensure_ascii=False),
            duties=json.dumps(analysis.get("duties", []), ensure_ascii=False),
            culture_values=json.dumps(analysis.get("culture_values", []), ensure_ascii=False),
        )
