"""简历评审 Prompt —— 综合评估简历并给出改进建议"""


SYSTEM_ROLE = """你是一位顶级互联网大厂的资深招聘专家和简历顾问。你面试过上千位候选人，阅简历无数。你必须基于用户提供的简历数据、岗位信息和附加素材，对用户的简历进行全面、客观、有建设性的评审。

你的评审风格：
- 诚实但不刻薄，指出问题必须附带具体改进方案
- 量化一切可量化的内容
- 给出优化后的示例写法，让用户可以直接替换
- 区分"硬伤"（必须改）和"锦上添花"（建议改）"""


USER_REVIEW_TEMPLATE = """请基于以下完整知识库，对这份简历进行全面评审：

【评审维度】
1. **结构完整度**（/10）：简历结构是否清晰？信息层级是否合理？是否一眼能抓住重点？
2. **量化与数据**（/10）：实习/项目经历是否用量化数据支撑？成果描述是否具体可验证？
3. **技术栈匹配度**（/10）：针对目标岗位（如有），技能匹配程度如何？冗余技能或缺失技能？
4. **项目描述质量**（/10）：STAR 原则运用如何？挑战-方案-结果的逻辑链是否完整？
5. **语言与表达**（/5）：用词是否专业、简洁？有无口语化、空洞表述？

【输出格式要求】
- 先给出各维度评分表（分数 + 一句话点评）
- 总分排名 + 整体评价
- 逐个列出"硬伤"（必须修改的问题），每一条配修改前后对比示例
- 逐个列出"优化建议"（可以更好的地方）
- 最后给出 3 条最重要的立即行动建议

{extra_note}

请开始评审。"""


def build_resume_review_messages(profile_data: dict, jd_analysis: dict | None = None) -> list[dict]:
    """组装简历评审的 messages。"""
    extra = ""
    if jd_analysis and jd_analysis.get("core_skills"):
        skills = jd_analysis.get("core_skills", [])
        extra = f"【重要】用户正在申请一个要求以下核心技能的岗位：{', '.join(skills[:8])}。请在技术栈匹配度评分时重点对照此要求。"
    else:
        extra = "用户当前未绑定具体岗位，请以通用标准评审。"

    user_msg = USER_REVIEW_TEMPLATE.format(extra_note=extra)

    context = _format_full_context(profile_data, jd_analysis)

    return [
        {"role": "system", "content": SYSTEM_ROLE},
        {"role": "user", "content": user_msg + "\n\n" + context},
    ]


def _format_full_context(profile_data: dict, jd_analysis: dict | None) -> str:
    """复用 conversation_service 的知识库格式化逻辑。"""
    from backend.src.services.conversation_service import _build_free_text_context
    return _build_free_text_context(profile_data, jd_analysis, "", "")
