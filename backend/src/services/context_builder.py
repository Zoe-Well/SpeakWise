"""统一的知识库与会话上下文构建器。"""

from dataclasses import dataclass
import json

from sqlmodel import Session, select

from backend.src.models.document import SourceDocument
from backend.src.models.job_context import JobContext
from backend.src.models.profile import UserProfile
from backend.src.models.session import ConversationSession, Message
from backend.src.services import profile_service
from backend.src.services.skill_categorizer import category_label


@dataclass(frozen=True)
class ContextBudgets:
    """各上下文分区的近似字符预算。

    中文场景下字符数比简单 token 猜测更稳定，也避免新增 tokenizer 依赖。
    """

    profile: int = 6000
    jd: int = 2500
    profile_documents: int = 5000
    jd_documents: int = 3000
    summary: int = 2000
    recent_history: int = 6000
    recent_messages: int = 8


DEFAULT_CONTEXT_BUDGETS = ContextBudgets()


def _clip(text: str, budget: int) -> str:
    if budget <= 0:
        return ""
    if len(text) <= budget:
        return text
    if budget == 1:
        return "…"
    return text[: budget - 1].rstrip() + "…"


def _allocate_documents(documents: list[SourceDocument], budget: int) -> list[dict]:
    """在同一类别总预算内公平分配多个附件，而不是每个附件各用一份预算。"""
    remaining = max(0, budget)
    result: list[dict] = []
    for index, document in enumerate(documents):
        if remaining <= 0:
            break
        documents_left = len(documents) - index
        share = max(1, remaining // documents_left)
        text = _clip(document.extracted_text or "", share)
        if text:
            result.append({"filename": document.filename, "text": text})
            remaining -= len(text)
    return result


class ContextBuilder:
    def __init__(self, db: Session | None, budgets: ContextBudgets = DEFAULT_CONTEXT_BUDGETS):
        self.db = db
        self.budgets = budgets

    def load_profile_data(self, profile_id: int) -> dict:
        if self.db is None:
            raise ValueError("load_profile_data requires a database session")

        profile = self.db.get(UserProfile, profile_id) or profile_service.get_active_profile(self.db)
        internships = profile_service.list_internships(self.db, profile.id)
        projects = profile_service.list_projects(self.db, profile.id)
        skills = profile_service.list_skills(self.db, profile.id)

        def load_documents(scope: str) -> list[SourceDocument]:
            return list(self.db.exec(
                select(SourceDocument)
                .where(SourceDocument.profile_id == profile.id)
                .where(SourceDocument.scope == scope)
                .where(SourceDocument.usage == "attach")
                .where(SourceDocument.is_active == True)  # noqa: E712
                .where(SourceDocument.extracted_text.isnot(None))  # type: ignore[arg-type]
                .order_by(SourceDocument.created_at.desc())
            ).all())

        return {
            "name": profile.name,
            "internships": [
                {
                    "company": item.company,
                    "position": item.position,
                    "achievements": json.loads(item.achievements or "[]"),
                }
                for item in internships
            ],
            "projects": [
                {
                    "name": item.name,
                    "role": item.role,
                    "tech_stack": json.loads(item.tech_stack or "[]"),
                    "challenge": item.challenge,
                    "solution": item.solution,
                    "result": item.result,
                }
                for item in projects
            ],
            "skills": [
                {"category": item.category, "name": item.name, "proficiency": item.proficiency}
                for item in skills
            ],
            "profile_docs": _allocate_documents(
                load_documents("profile"), self.budgets.profile_documents
            ),
            "jd_docs": _allocate_documents(
                load_documents("jd"), self.budgets.jd_documents
            ),
        }

    def load_active_jd(self, profile_id: int) -> dict | None:
        """JD 的唯一事实来源：当前 profile 下的 is_active 记录。"""
        if self.db is None:
            raise ValueError("load_active_jd requires a database session")
        context = self.db.exec(
            select(JobContext)
            .where(JobContext.profile_id == profile_id)
            .where(JobContext.is_active == True)  # noqa: E712
            .order_by(JobContext.id.desc())
        ).first()
        return context.to_analysis_dict() if context else None

    def build_history_messages(
        self,
        session_id: int,
        *,
        exclude_message_id: int | None = None,
    ) -> list[dict]:
        """返回一份不重复的“滚动摘要 + 最近原文消息”历史。"""
        if self.db is None:
            return []
        conversation = self.db.get(ConversationSession, session_id)
        if not conversation:
            return []

        statement = select(Message).where(Message.session_id == session_id)
        if conversation.summary_up_to_message_id:
            statement = statement.where(Message.id > conversation.summary_up_to_message_id)
        if exclude_message_id:
            statement = statement.where(Message.id != exclude_message_id)
        messages = list(self.db.exec(
            statement.order_by(Message.created_at.desc(), Message.id.desc())
            .limit(self.budgets.recent_messages)
        ).all())[::-1]

        # 从最新消息向前分配历史预算，再恢复时间顺序。
        remaining = self.budgets.recent_history
        clipped_reversed: list[dict] = []
        for message in reversed(messages):
            if remaining <= 0:
                break
            content = _clip(message.content.strip(), remaining)
            if content:
                clipped_reversed.append({"role": message.role, "content": content})
                remaining -= len(content)
        recent = list(reversed(clipped_reversed))

        result: list[dict] = []
        if conversation.memory_summary:
            result.append({
                "role": "system",
                "content": "【较早对话摘要】\n" + _clip(
                    conversation.memory_summary, self.budgets.summary
                ),
            })
        result.extend(recent)
        return result

    def format_profile(self, profile_data: dict, *, include_documents: bool = True) -> str:
        parts = [f"姓名：{profile_data.get('name', '')}"]
        for experience in profile_data.get("internships", []):
            achievements = experience.get("achievements", [])
            parts.append(
                f"实习：{experience.get('company', '')} {experience.get('position', '')}"
                f" · 成果：{'；'.join(achievements[:3])}"
            )
        for project in profile_data.get("projects", []):
            parts.append(
                f"项目：{project.get('name', '')}（角色：{project.get('role', '')}）"
                f" · 挑战：{project.get('challenge', '')}"
                f" · 方案：{project.get('solution', '')}"
                f" · 结果：{project.get('result', '')}"
            )
        skills_by_category: dict[str, list[str]] = {}
        for skill in profile_data.get("skills", []):
            skills_by_category.setdefault(skill.get("category", "other"), []).append(
                f"{skill.get('name', '')}({skill.get('proficiency', '')})"
            )
        for category, skills in skills_by_category.items():
            parts.append(f"技能-{category_label(category)}：{', '.join(skills)}")

        rendered = _clip("\n".join(parts), self.budgets.profile)
        if not include_documents:
            return rendered
        document_text = self.format_documents(profile_data)
        return rendered + ("\n" + document_text if document_text else "")

    def format_documents(self, profile_data: dict) -> str:
        parts = []
        for document in profile_data.get("profile_docs", []):
            parts.append(f"【附加个人素材-{document['filename']}】\n{document['text']}")
        for document in profile_data.get("jd_docs", []):
            parts.append(f"【附加公司素材-{document['filename']}】\n{document['text']}")
        return "\n".join(parts)

    def format_jd(self, jd_analysis: dict | None) -> str:
        if not jd_analysis:
            return "通用面试模式（未提供岗位信息）"
        parts = []
        if jd_analysis.get("core_skills"):
            parts.append(f"核心技能要求：{', '.join(jd_analysis['core_skills'])}")
        if jd_analysis.get("duties"):
            parts.append(f"主要职责：{', '.join(jd_analysis['duties'])}")
        if jd_analysis.get("culture_values"):
            parts.append(f"公司价值观/方向：{', '.join(jd_analysis['culture_values'])}")
        return _clip("；".join(parts), self.budgets.jd) or "通用面试模式（未提供岗位信息）"

    def build_knowledge_context(
        self,
        profile_data: dict,
        jd_analysis: dict | None,
        content: str = "",
    ) -> str:
        sections = ["【用户简历】\n" + self.format_profile(profile_data, include_documents=False)]
        sections.append("【目标岗位信息】\n" + self.format_jd(jd_analysis))
        documents = self.format_documents(profile_data)
        if documents:
            sections.append(documents)
        if content:
            sections.append(f"【当前问题】\n{content}")
        return "\n\n".join(sections)
