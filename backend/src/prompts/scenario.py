"""场景题回答生成 —— STAR 框架 Prompt 模板（思考链由模型原生 reasoning 提供，无需 --- 分隔符）"""

SCENARIO_SYSTEM = """你是一位顶级互联网大厂的资深面试教练。你必须基于用户提供的真实经历，生成结构清晰、步骤明确、可执行的场景题回答。采用 STAR 式框架。你必须锚定用户真实的项目或实习经历。绝不编造完全无关的技术或经历。语气：危机处理沉稳克制，优化提升进取积极。

【多轮对话】这是一段持续面试准备对话的一部分。如果用户重复请求类似场景或问题：
- 优先检查对话历史中你上次使用的案例，避免重复使用相同经历
- 如果用户没有明确指定新方向，可以基于上次回答进行微调优化
- 除非用户明确要求"换个例子"或"不同的思路"，否则以迭代改进为主"""


def build_scenario_messages(profile_data: dict, question: str, jd_analysis: dict | None = None, template_rules: dict | None = None, tone: str = "auto") -> list[dict]:
    """组装场景题生成的 messages。"""
    from backend.src.services.context_builder import ContextBuilder
    builder = ContextBuilder(None)
    # Detect tone from question keywords
    if tone == "auto":
        optimistic_keywords = ["优化", "提升", "改进", "效率", "创新", "增长"]
        tone_instruction = ("优化提升类 —— 用进取积极的语气" if any(kw in question for kw in optimistic_keywords)
                            else "危机/故障处理类 —— 用沉稳克制的语气")
    else:
        tone_instruction = tone

    context_parts = [
        f"【用户经历】：{_fmt(profile_data)}",
        f"【面试问题】：{question}",
        f"【语气要求】：{tone_instruction}",
    ]

    # Inject JD context if available
    if jd_analysis:
        context_parts.append("【目标岗位信息】：" + builder.format_jd(jd_analysis))
    else:
        context_parts.append("【模式】：通用面试模式（未提供岗位信息）")

    context_parts.append("行动部分必须包含至少 3 个明确编号步骤，步骤上下文必须锚定用户真实经历。")

    # Apply template rules if provided
    if template_rules:
        if template_rules.get("structure"):
            context_parts.append(f"用户指定的结构规则（必须遵循）：{template_rules['structure']}")
        if template_rules.get("style"):
            context_parts.append(f"用户指定的风格规则：{template_rules['style']}")

    return [
        {"role": "system", "content": SCENARIO_SYSTEM},
        {"role": "user", "content": "\n".join(context_parts)},
    ]


def _fmt(data: dict) -> str:
    from backend.src.services.context_builder import ContextBuilder
    return ContextBuilder(None).format_profile(data)
