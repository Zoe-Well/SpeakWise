"""技术面试题生成 —— 结构化解题 Prompt 模板"""

TECH_SYSTEM = """你是一位顶级互联网大厂的资深面试教练，擅长技术面试辅导。你必须基于用户提供的真实经历和技能，生成结构清晰、步骤明确的技术面试回答。

技术面试回答格式：
1. 【理解题意】：用 1-2 句确认对题目的理解，展示沟通能力
2. 【思路分析】：给出解题思路，分析时间/空间复杂度，对比不同方案
3. 【代码实现】：给出完整可运行代码，包含必要的注释
4. 【测试用例】：给出 2-3 个测试用例（含边界情况）
5. 【面试追问】：预判面试官可能的追问方向并给出应对思路

【多轮对话】这是一段持续面试准备对话的一部分。如果用户重复提问或追问类似技术点：
- 检查对话历史中你上次的技术分析，在此基础上深化或从不同角度补充
- 避免简单地重新生成一遍相同的回答
- 如果用户没有明确提出新的技术要求，可以聚焦于上次未展开的细节

要求：
- 技术细节必须准确，代码可以直接运行
- 结合用户简历中的技术栈和项目经验，展示匹配度
- 如果题目涉及用户项目中的技术，主动建立联系
- 回答风格专业但不过于学术，像真正的面试对话"""


def build_technical_messages(profile_data: dict, question: str, jd_analysis: dict | None = None, template_rules: dict | None = None) -> list[dict]:
    """组装技术面试题的 messages。"""
    from backend.src.services.context_builder import ContextBuilder
    builder = ContextBuilder(None)

    context_parts = [
        f"【用户经历】：{builder.format_profile(profile_data)}",
        f"【技术面试问题】：{question}",
    ]

    # Inject JD context if available
    if jd_analysis:
        context_parts.append("【目标岗位信息】：" + builder.format_jd(jd_analysis))
    else:
        context_parts.append("【模式】：通用技术面试模式（未提供岗位信息）")

    # Apply template rules
    if template_rules:
        if template_rules.get("structure"):
            context_parts.append(f"用户指定的结构规则（必须遵循）：{template_rules['structure']}")
        if template_rules.get("style"):
            context_parts.append(f"用户指定的风格规则：{template_rules['style']}")

    return [
        {"role": "system", "content": TECH_SYSTEM},
        {"role": "user", "content": "\n".join(context_parts)},
    ]
