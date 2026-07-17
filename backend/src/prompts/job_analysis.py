"""岗位解析 Prompt —— 深度分析 JD + 给出面试策略建议"""


SYSTEM_ROLE = """你是一位顶级互联网大厂的资深面试教练。你帮助候选人快速把握岗位要点，制定面试的整体策略方向。

你的风格：精炼、概括、直击要点。不说废话，每条建议都可直接指导面试准备。"""


USER_ANALYSIS_TEMPLATE = """请基于用户知识库进行岗位解析和面试整体把控：

【输出要求】

**一、岗位画像（2-3 句话）**
- 用你自己的话概括这个岗位的核心定位和要解决的关键问题

**二、核心要求摘要**
- 将 JD 中的关键要求浓缩为一句话清单，不做分层

**三、简历匹配概览**
- 用户的简历强项是什么（与岗位最匹配的 2-3 个点）
- 需要注意或弥补的弱项是什么（1-2 个点）

**四、面试整体策略**
- 用户应该突出什么能力/经历
- 用户应该回避或弱化什么方向
- 整体的面试准备建议和节奏把控

{extra_note}

请简明扼要，控制在 800 字以内。"""


def build_job_analysis_messages(profile_data: dict, jd_analysis: dict | None = None) -> list[dict]:
    """组装岗位解析的 messages。"""
    extra = ""
    if not jd_analysis or not jd_analysis.get("core_skills"):
        extra = "⚠ 用户当前未绑定具体岗位 JD。请基于用户简历给出通用面试策略建议，告诉用户绑定 JD 后可以获得更精准的分析。"
    else:
        extra = "用户已绑定岗位 JD，请基于 JD 与简历的对照进行精准分析。"

    user_msg = USER_ANALYSIS_TEMPLATE.format(extra_note=extra)

    from backend.src.services.conversation_service import _build_free_text_context
    context = _build_free_text_context(profile_data, jd_analysis, "", "")

    return [
        {"role": "system", "content": SYSTEM_ROLE},
        {"role": "user", "content": user_msg + "\n\n" + context},
    ]
