"""自我介绍生成 —— 分层 Prompt 模板（思考链由模型原生 reasoning 提供，无需 --- 分隔符）"""

SYSTEM_ROLE = """你是一位顶级互联网大厂的资深面试教练。你必须基于用户提供的简历数据与岗位上下文生成流利、精简、自然的自我介绍。你必须基于事实，但擅长用叙事技巧包装经历。绝不编造与用户无关的工作经历。

【多轮对话】这是一段持续面试准备对话的一部分。如果用户重复请求自我介绍或类似内容：
- 检查对话历史中你上次的回答，以此为基础进行优化调整
- 可以换一个角度、换一组经历、或根据用户的新反馈来迭代
- 除非用户明确要求"全新的"或"完全不同的"，否则不需要从零重新构思"""

USER_CONTROL_TEMPLATE = """请按以下要求生成完整的自我介绍：
1. 【概述】：挑选简历中最核心的 2 段经历开头。
2. 【能力总结】：提炼 3 个适配岗位的核心技能。强匹配用数据证实，弱匹配从"学习/个人实践/底层逻辑"角度弥补。
3. 【业务匹配】：引入对 JD 的理解，说明自身能力如何支撑该岗位。
朗读时长约 1-2 分钟，总字数控制在 300-400 字。自然流利。
{extra_requirements}"""


def build_intro_messages(profile_data: dict, jd_analysis: dict | None, extra: str = "", template_rules: dict | None = None) -> list[dict]:
    """组装自我介绍生成的 messages。如果提供 template_rules，覆盖默认结构/风格。"""
    from backend.src.services.context_builder import ContextBuilder
    builder = ContextBuilder(None)
    # Apply template rules if provided
    struct_override = ""
    style_override = ""
    if template_rules:
        if template_rules.get("structure"):
            struct_override = f"用户指定的结构规则（必须遵循）：{template_rules['structure']}"
        if template_rules.get("style"):
            style_override = f"用户指定的风格规则：{template_rules['style']}"

    user_ctrl = USER_CONTROL_TEMPLATE.format(
        extra_requirements=f"额外要求：{extra}" if extra else ""
    )

    context_parts = [f"【用户简历】：{_format_profile(profile_data)}"]
    if struct_override:
        context_parts.append(struct_override.strip())
    if style_override:
        context_parts.append(style_override.strip())
    if jd_analysis:
        context_parts.append(f"【目标岗位】：{builder.format_jd(jd_analysis)}")
    else:
        context_parts.append("【模式】：通用面试模式（未提供岗位信息）")

    return [
        {"role": "system", "content": SYSTEM_ROLE},
        {"role": "system", "content": user_ctrl},
        {"role": "user", "content": "\n".join(context_parts)},
    ]


def _format_profile(data: dict) -> str:
    """统一使用 ContextBuilder 的预算与知识格式。"""
    from backend.src.services.context_builder import ContextBuilder
    return ContextBuilder(None).format_profile(data)
