"""模拟面试 Prompt 模板"""


def _format_history(recent_msgs: list[dict]) -> str:
    """将最近消息格式化为面试上下文。"""
    if not recent_msgs:
        return "（暂无前序问答）"
    lines = ["【面试前序问答】"]
    for m in recent_msgs:
        role = "面试官" if m["role"] == "assistant" else "候选人"
        lines.append(f"{role}: {m['content'][:500]}")
    return "\n".join(lines)


def build_start_prompt(profile_data: dict, jd_analysis: dict | None) -> list[dict]:
    """生成第一个面试问题。"""
    from backend.src.services.conversation_service import _build_free_text_context

    system = """你是一位专业、友善的面试官。你正在进行一场模拟面试。

你的任务：
1. 基于候选人的简历和岗位要求，提出一个开放性的面试问题
2. 问题应该有针对性，考察候选人的真实能力和经验
3. 每个问题只问一件事，不要一口气问多个问题
4. 用自然的口语表达，像真实面试一样"""

    user_context = _build_free_text_context(profile_data, jd_analysis, "", "")
    user_msg = f"""请基于以下候选人信息，提出第一个面试问题。

{user_context}

要求：
- 问题聚焦于候选人的核心经历或技能
- 开放式提问，鼓励候选人展开回答
- 语气自然、专业
- 只输出问题本身，不要加前缀或解释"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]


def build_evaluate_prompt(
    profile_data: dict,
    jd_analysis: dict | None,
    question: str,
    user_answer: str,
    recent_msgs: list[dict] | None = None,
) -> list[dict]:
    """评审用户回答 + 给出参考回答（不含下一题）。"""
    from backend.src.services.conversation_service import _build_free_text_context

    system = """你是一位专业、友善的面试官。你正在评估候选人的回答。

你的评审风格：
- 先肯定优点，再指出可以改进的地方
- 建议具体、可操作
- 参考回答应该展示高水平的表达方式"""

    history = _format_history(recent_msgs or [])
    user_context = _build_free_text_context(profile_data, jd_analysis, "", "")

    user_msg = f"""{user_context}

{history}

【当前问题】{question}

【候选人回答】{user_answer}

请按以下结构输出：

**评审意见**
- 优点：（1-2 点）
- 可改进：（1-2 点具体建议）

**参考回答**
给出一个更完善的参考回答（200-400 字）"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]


def build_reference_prompt(
    profile_data: dict,
    jd_analysis: dict | None,
    question: str,
    recent_msgs: list[dict] | None = None,
) -> list[dict]:
    """仅生成参考回答（不含下一题）。"""
    from backend.src.services.conversation_service import _build_free_text_context

    system = """你是一位专业、友善的面试官。候选人选择不回答当前问题，直接查看参考回答。"""

    history = _format_history(recent_msgs or [])
    user_context = _build_free_text_context(profile_data, jd_analysis, "", "")

    user_msg = f"""{user_context}

{history}

【当前问题】{question}

候选人选择跳过回答，直接看参考。请输出：

**参考回答**
给出一个完善的参考回答（200-400 字）"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]


def build_next_question_prompt(
    profile_data: dict,
    jd_analysis: dict | None,
    recent_msgs: list[dict] | None = None,
) -> list[dict]:
    """基于前序 QA 生成下一个面试问题。"""
    from backend.src.services.conversation_service import _build_free_text_context

    system = """你是一位专业、友善的面试官。请基于前序对话，提出下一个面试问题。

你的任务：
- 问题要自然衔接到新的考察方向，不重复已讨论过的话题
- 每个问题只问一件事
- 用自然的口语表达
- 只输出问题本身，不要加前缀或解释"""

    history = _format_history(recent_msgs or [])
    user_context = _build_free_text_context(profile_data, jd_analysis, "", "")

    user_msg = f"""{user_context}

{history}

请基于以上对话历史，提出下一个面试问题。注意：
- 不要重复已经讨论过的话题
- 自然衔接到新的考察方向
- 只输出问题本身"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]


def build_replace_prompt(
    profile_data: dict,
    jd_analysis: dict | None,
    question: str,
    recent_msgs: list[dict] | None = None,
) -> list[dict]:
    """忽略当前问题，生成替换题。"""
    from backend.src.services.conversation_service import _build_free_text_context

    system = """你是一位专业、友善的面试官。候选人觉得当前问题不合适，你需要换一个问题。"""

    history = _format_history(recent_msgs or [])
    user_context = _build_free_text_context(profile_data, jd_analysis, "", "")

    user_msg = f"""{user_context}

{history}

【已跳过的问题】{question}

候选人觉得以上问题不合适。请换一个方向，提出一个新的面试问题。
- 不要重复已经讨论过的话题
- 选择一个不同的考察角度
- 只输出问题本身"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]


def build_summary_prompt(all_qa: list[dict]) -> list[dict]:
    """将全部有效 QA 汇总为结构化文档。"""
    qa_text = []
    for i, item in enumerate(all_qa, 1):
        qa_type = item.get("qa_type", "answered")
        qa_text.append(f"## Q{i}: {item.get('question', '')}")

        if qa_type == "answered":
            qa_text.append(f"- 用户回答: {item.get('user_answer', '')[:1000]}")
            if item.get("evaluation"):
                qa_text.append(f"- AI 评审: {item['evaluation'][:800]}")
        else:
            qa_text.append("- （用户未回答，仅查看参考）")

        if item.get("reference_answer"):
            qa_text.append(f"- 参考回答: {item['reference_answer'][:800]}")
        qa_text.append("")

    system = "你是一位面试教练。请将以下模拟面试记录整理为一份专业的面试总结文档。"
    user_msg = f"""请将以下模拟面试记录整理为一份结构化的面试总结。保持原有结构，适度精简冗余内容。

{chr(10).join(qa_text)}"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]
