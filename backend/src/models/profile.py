"""核心数据模型：UserProfile, Internship, Project, Skill"""

from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class UserProfile(SQLModel, table=True):
    __tablename__ = "user_profiles"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(default="未命名", max_length=100)
    phone: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=200)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Internship(SQLModel, table=True):
    __tablename__ = "internships"

    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="user_profiles.id")
    company: str = Field(max_length=200)
    position: str = Field(max_length=200)
    start_date: str = Field(max_length=20)
    end_date: Optional[str] = Field(default=None, max_length=20)
    achievements: str = Field(default="[]")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Project(SQLModel, table=True):
    __tablename__ = "projects"

    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="user_profiles.id")
    type: str = Field(max_length=20)
    name: str = Field(max_length=200)
    role: str = Field(max_length=100)
    tech_stack: str = Field(default="[]")
    challenge: str = Field(default="")
    solution: str = Field(default="")
    result: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Skill(SQLModel, table=True):
    __tablename__ = "skills"

    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="user_profiles.id")
    category: str = Field(max_length=30)
    name: str = Field(max_length=100)
    proficiency: str = Field(max_length=20)
    created_at: datetime = Field(default_factory=datetime.utcnow)
