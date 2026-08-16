"""会话滚动摘要。旧消息压缩后持久化，最近消息保留原文。"""

import logging

from sqlmodel import Session, select

from backend.src.llm.client import llm_client
from backend.src.models.session import ConversationSession, Message
from backend.src.services.context_builder import DEFAULT_CONTEXT_BUDGETS, _clip

logger = logging.getLogger("speakwise")


async def refresh_conversation_summary(
    db: Session,
    session_id: int,
    *,
    exclude_message_id: int | None = None,
) -> str | None:
    """把最近消息窗口之前的新增消息合并进滚动摘要。

    摘要失败不会阻断主回答，ContextBuilder 会退化为最近原文消息。
    """
    conversation = db.get(ConversationSession, session_id)
    if not conversation:
        return None

    statement = select(Message).where(Message.session_id == session_id)
    if exclude_message_id:
        statement = statement.where(Message.id != exclude_message_id)
    all_messages = list(db.exec(
        statement.order_by(Message.created_at, Message.id)
    ).all())
    keep = DEFAULT_CONTEXT_BUDGETS.recent_messages
    older = all_messages[:-keep] if len(all_messages) > keep else []
    if conversation.summary_up_to_message_id:
        older = [m for m in older if m.id and m.id > conversation.summary_up_to_message_id]
    if not older:
        return conversation.memory_summary

    transcript = "\n".join(
        f"{'用户' if message.role == 'user' else '助手'}：{message.content}"
        for message in older
    )
    previous = conversation.memory_summary or "（无）"
    prompt = f"""请更新面试准备会话的事实摘要。

要求：
- 只保留用户背景、目标、偏好、已讨论结论和仍待解决的问题
- 不补充对话中没有的信息
- 合并重复信息，使用简洁中文
- 控制在 {DEFAULT_CONTEXT_BUDGETS.summary} 字以内

【已有摘要】
{_clip(previous, DEFAULT_CONTEXT_BUDGETS.summary)}

【新增旧对话】
{_clip(transcript, 8000)}
"""
    try:
        summary = await llm_client.chat(
            [
                {"role": "system", "content": "你是可靠的会话记忆整理器。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            model=llm_client.fast_model(),
        )
    except Exception as exc:
        logger.warning("会话摘要更新失败: %s", exc)
        return conversation.memory_summary

    conversation.memory_summary = _clip(summary.strip(), DEFAULT_CONTEXT_BUDGETS.summary)
    conversation.summary_up_to_message_id = older[-1].id
    db.add(conversation)
    db.commit()
    return conversation.memory_summary
