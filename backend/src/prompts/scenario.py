"""场景题回答生成 —— STAR 框架 Prompt 模板（思考链由模型原生 reasoning 提供，无需 --- 分隔符）"""

SCENARIO_SYSTEM = """你是一位顶级互联网大厂的资深面试教练。你必须基于用户提供的真实经历，生成结构清晰、步骤明确、可执行的场景题回答。采用 STAR 式框架。你必须锚定用户真实的项目或实习经历。绝不编造完全无关的技术或经历。语气：危机处理沉稳克制，优化提升进取积极。"""


def build_scenario_messages(profile_data: dict, question: str, jd_analysis: dict | None = None, template_rules: dict | None = None, tone: str = "auto") -> list[dict]:
    """组装场景题生成的 messages。"""
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
        parts = []
        if jd_analysis.get("core_skills"):
            parts.append(f"核心技能要求：{', '.join(jd_analysis['core_skills'])}")
        if jd_analysis.get("duties"):
            parts.append(f"主要职责：{', '.join(jd_analysis['duties'])}")
        if jd_analysis.get("culture_values"):
            parts.append(f"公司价值观/方向：{', '.join(jd_analysis['culture_values'])}")
        if parts:
            context_parts.append("【目标岗位信息】：" + "；".join(parts))
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
    parts = []
    for exp in data.get("internships", []):
        parts.append(f"实习：{exp['company']} {exp['position']}（{exp.get('achievements',[])}）")
    for proj in data.get("projects", []):
        parts.append(f"项目：{proj['name']} 角色：{proj['role']} 挑战：{proj['challenge']} 方案：{proj['solution']} 结果：{proj['result']}")

    # Include attached document text as knowledge base
    for doc in data.get("profile_docs", []):
        parts.append(f"【附加个人素材-{doc['filename']}】：{doc['text']}")
    for doc in data.get("jd_docs", []):
        parts.append(f"【附加公司素材-{doc['filename']}】：{doc['text']}")

    return "\n".join(parts)
